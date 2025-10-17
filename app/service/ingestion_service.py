from __future__ import annotations

import re
from typing import List, Sequence

import httpx
from loguru import logger

from app.api.dto import IngestionMessage
from app.entities.entity import UrlEntity, UrlStatus
from app.repository.repository import Repository
from pkg.embedding.client import VoyageEmbeddingClient

CHUNK_SIZE = 1200
FETCH_TIMEOUT_SECONDS = 10.0

SCRIPT_RE = re.compile(r"<script.*?>.*?</script>", re.IGNORECASE | re.DOTALL)
STYLE_RE = re.compile(r"<style.*?>.*?</style>", re.IGNORECASE | re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")
SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+")


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE) -> List[str]:
    if not text:
        return []

    clean = text.strip()
    if len(clean) <= chunk_size:
        return [clean]

    chunks: List[str] = []
    buffer: List[str] = []
    buffer_len = 0

    sentences = SENTENCE_BOUNDARY_RE.split(clean)

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        sentence_len = len(sentence)
        if sentence_len > chunk_size:
            if buffer:
                chunks.append(" ".join(buffer))
                buffer.clear()
                buffer_len = 0
            for idx in range(0, sentence_len, chunk_size):
                chunk = sentence[idx : idx + chunk_size]
                if chunk:
                    chunks.append(chunk)
            continue

        prospective_len = buffer_len + (1 if buffer else 0) + sentence_len
        if prospective_len <= chunk_size:
            buffer.append(sentence)
            buffer_len = prospective_len
        else:
            if buffer:
                chunks.append(" ".join(buffer))
            buffer = [sentence]
            buffer_len = sentence_len

    if buffer:
        chunks.append(" ".join(buffer))

    return chunks


async def fetch_plain_text(url: str, timeout: float = FETCH_TIMEOUT_SECONDS) -> str:
    async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
        response = await client.get(url)
        response.raise_for_status()
        text = response.text
    text = SCRIPT_RE.sub(" ", text)
    text = STYLE_RE.sub(" ", text)
    text = TAG_RE.sub(" ", text)
    text = WHITESPACE_RE.sub(" ", text)
    return text.strip()


class IngestionService:
    """Coordinates URL ingestion and downstream processing."""

    def __init__(self, repository: Repository, embedding_client: VoyageEmbeddingClient) -> None:
        self._repository = repository
        self._embedding_client = embedding_client

    async def ingest_urls(self, urls: Sequence[str]) -> List[UrlEntity]:
        if not urls:
            return []
        return await self._repository.create_urls(urls)

    async def process_job(self, job: IngestionMessage) -> None:
        logger.info("Processing URL %s", job.url)
        try:
            await self._repository.update_status(job.url_id, UrlStatus.FETCHING)
            content = await fetch_plain_text(str(job.url))
            content_entity = await self._repository.upsert_content(job.url_id, content)

            await self._repository.update_status(job.url_id, UrlStatus.CHUNKING)
            chunks = chunk_text(content, CHUNK_SIZE)
            chunk_entities = await self._repository.create_chunks(job.url_id, chunks, content_id=content_entity.id)

            if chunk_entities:
                await self._repository.update_status(job.url_id, UrlStatus.EMBEDDING)
                vectors = await self._embedding_client.embed_document(chunks)

                if len(vectors) != len(chunk_entities):
                    logger.warning(
                        "Embedding count mismatch for %s: %s vectors vs %s chunks",
                        job.url,
                        len(vectors),
                        len(chunk_entities),
                    )

                for chunk_entity, vector in zip(chunk_entities, vectors):
                    await self._repository.create_embedding(chunk_entity.id, vector)
                    await self._repository.mark_chunk_embedded(chunk_entity.id)

            await self._repository.update_status(job.url_id, UrlStatus.COMPLETED)
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.exception("Failed to process URL %s: %s", job.url, exc)
            raise exc
