from __future__ import annotations

import asyncio

from loguru import logger

from app.api.subscriber import listen_for_jobs
from app.repository.repository import Repository
from app.service.ingestion_service import IngestionService
from pkg.config.config import Settings
from pkg.embedding.client import VoyageEmbeddingClient
from pkg.postgres.client import PostgresClient
from pkg.redis.client import RedisQueue

QUEUE_BLOCK_TIMEOUT = 5


def build_components(settings: Settings) -> tuple[Repository, IngestionService, PostgresClient, RedisQueue]:
    postgres_client = PostgresClient(
        user=settings.postgres_db_user,
        password=settings.postgres_db_password,
        host=settings.postgres_db_host,
        port=settings.postgres_db_port,
        database=settings.postgres_db_name,
    )

    redis_queue = RedisQueue(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
        queue_name=settings.redis_queue_name,
    )

    repository = Repository(postgres_client, redis_queue)
    embedding_client = VoyageEmbeddingClient(api_key=settings.voyage_api_key)
    service = IngestionService(repository=repository, embedding_client=embedding_client)

    return repository, service, postgres_client, redis_queue


async def main() -> None:
    settings = Settings()

    repository, service, postgres_client, redis_queue = build_components(settings)

    await postgres_client.connect()
    await postgres_client.create_tables()
    await redis_queue.connect()

    logger.info("Worker started; awaiting jobs on {queue}", queue=redis_queue.queue_name)

    try:
        await listen_for_jobs(repository, service, timeout=QUEUE_BLOCK_TIMEOUT)
    except asyncio.CancelledError:
        logger.info("Worker cancelled")
    finally:
        await redis_queue.close()
        await postgres_client.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker stopped by user")
