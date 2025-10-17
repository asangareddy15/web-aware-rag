from __future__ import annotations

from typing import Iterable, Sequence
from uuid import UUID

from loguru import logger
from sqlalchemy import Select, select, update

from app.api.dto import IngestionMessage
from app.entities.entity import (
    ChunkEntity,
    ChunkRetrieval,
    ContentEntity,
    EmbeddingEntity,
    UrlEntity,
    UrlStatus,
)
from app.repository.models.tables import (
    ChunkModel,
    ContentModel,
    EmbeddingModel,
    UrlModel,
    UrlStatusEnum,
)
from pkg.postgres.client import PostgresClient
from pkg.redis import RedisQueue


def _to_url_entity(model: UrlModel) -> UrlEntity:
    return UrlEntity(
        id=model.id,
        url=model.url,
        status=UrlStatus(model.status.value),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _to_content_entity(model: ContentModel) -> ContentEntity:
    return ContentEntity(
        id=model.id,
        url_id=model.url_id,
        content=model.content,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _to_chunk_entity(model: ChunkModel) -> ChunkEntity:
    return ChunkEntity(
        id=model.id,
        url_id=model.url_id,
        chunk_content=model.chunk_content,
        is_embedded=model.is_embedded,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _to_embedding_entity(model: EmbeddingModel) -> EmbeddingEntity:
    return EmbeddingEntity(
        id=model.id,
        chunk_id=model.chunk_id,
        vector=list(model.vector),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class Repository:
    """Coordinates persistence and queue operations for ingestion."""

    def __init__(self, postgres: PostgresClient, queue: RedisQueue) -> None:
        self._postgres = postgres
        self._queue = queue

    async def create_urls(self, urls: Sequence[str]) -> list[UrlEntity]:
        created: list[UrlEntity] = []
        messages: list[IngestionMessage] = []

        async with self._postgres.get_session() as session:
            for url in urls:
                existing_stmt = select(UrlModel).where(UrlModel.url == url)
                existing = await session.execute(existing_stmt)
                model = existing.scalar_one_or_none()
                if model:
                    entity = _to_url_entity(model)
                    created.append(entity)
                    if entity.status in {UrlStatus.PENDING, UrlStatus.FAILED}:
                        messages.append(IngestionMessage(url_id=entity.id, url=entity.url))
                    continue

                model = UrlModel(url=url, status=UrlStatusEnum.PENDING)
                session.add(model)
                await session.flush()
                entity = _to_url_entity(model)
                created.append(entity)
                messages.append(IngestionMessage(url_id=entity.id, url=entity.url))

        for message in messages:
            await self._queue.enqueue(message.model_dump(mode="json"))
            logger.info("Queued ingestion message for %s", message.url)

        return created

    async def update_status(self, url_id: UUID, status: UrlStatus) -> None:
        async with self._postgres.get_session() as session:
            query = (
                update(UrlModel)
                .where(UrlModel.id == url_id)
                .values(status=UrlStatusEnum(status.value))
                .execution_options(synchronize_session="fetch")
            )
            await session.execute(query)

    async def get_url(self, url_id: UUID) -> UrlEntity | None:
        async with self._postgres.get_session() as session:
            stmt: Select = select(UrlModel).where(UrlModel.id == url_id)
            result = await session.execute(stmt)
            model = result.scalar_one_or_none()
            return _to_url_entity(model) if model else None

    async def upsert_content(self, url_id: UUID, content: str) -> ContentEntity:
        async with self._postgres.get_session() as session:
            stmt: Select = select(ContentModel).where(ContentModel.url_id == url_id)
            result = await session.execute(stmt)
            model = result.scalar_one_or_none()
            if model:
                model.content = content
            else:
                model = ContentModel(url_id=url_id, content=content)
                session.add(model)
            await session.flush()
            return _to_content_entity(model)

    async def create_chunks(
        self,
        url_id: UUID,
        chunks: Iterable[str],
        content_id: UUID | None = None,
    ) -> list[ChunkEntity]:
        async with self._postgres.get_session() as session:
            records: list[ChunkModel] = []
            for chunk_text in chunks:
                model = ChunkModel(
                    url_id=url_id,
                    content_id=content_id,
                    chunk_content=chunk_text,
                    is_embedded=False,
                )
                session.add(model)
                records.append(model)
            if not records:
                return []
            await session.flush()
            return [_to_chunk_entity(model) for model in records]

    async def mark_chunk_embedded(self, chunk_id: UUID) -> None:
        async with self._postgres.get_session() as session:
            query = (
                update(ChunkModel)
                .where(ChunkModel.id == chunk_id)
                .values(is_embedded=True)
                .execution_options(synchronize_session="fetch")
            )
            await session.execute(query)

    async def create_embedding(self, chunk_id: UUID, vector: list[float]) -> EmbeddingEntity:
        async with self._postgres.get_session() as session:
            model = EmbeddingModel(chunk_id=chunk_id, vector=vector)
            session.add(model)
            await session.flush()
            return _to_embedding_entity(model)

    async def dequeue_ingestion(self, timeout: int = 5) -> IngestionMessage | None:
        payload = await self._queue.dequeue(timeout=timeout)
        if payload is None:
            return None
        return IngestionMessage.model_validate_json(payload)

    async def list_chunks_without_embeddings(self, url_id: UUID) -> list[ChunkEntity]:
        async with self._postgres.get_session() as session:
            stmt: Select = select(ChunkModel).where(
                ChunkModel.url_id == url_id,
                ChunkModel.is_embedded.is_(False),
            )
            result = await session.execute(stmt)
            models = result.scalars().all()
            return [_to_chunk_entity(model) for model in models]

    async def search_similar_chunks(
        self,
        query_vector: Sequence[float],
        limit: int = 8,
    ) -> list[ChunkRetrieval]:
        async with self._postgres.get_session() as session:
            distance_col = EmbeddingModel.vector.cosine_distance(query_vector).label("distance")
            stmt: Select = (
                select(ChunkModel, UrlModel.url, distance_col)
                .join(EmbeddingModel, EmbeddingModel.chunk_id == ChunkModel.id)
                .join(UrlModel, UrlModel.id == ChunkModel.url_id)
                .where(
                    ChunkModel.is_embedded.is_(True),
                    UrlModel.status == UrlStatusEnum.COMPLETED,
                )
                .order_by(distance_col)
                .limit(limit)
            )
            result = await session.execute(stmt)
            rows = result.all()

        retrieved: list[ChunkRetrieval] = []
        for chunk_model, url, distance in rows:
            try:
                distance_value = float(distance) if distance is not None else float("inf")
            except (TypeError, ValueError):
                distance_value = float("inf")
            retrieved.append(
                ChunkRetrieval(
                    chunk=_to_chunk_entity(chunk_model),
                    url=str(url),
                    distance=distance_value,
                )
            )
        return retrieved
