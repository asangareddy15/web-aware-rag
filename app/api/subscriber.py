from __future__ import annotations

import asyncio

from loguru import logger

from app.repository.repository import Repository
from app.service.ingestion_service import IngestionService


async def listen_for_jobs(repository: Repository, service: IngestionService, timeout: int = 5) -> None:
    while True:
        message = await repository.dequeue_ingestion(timeout=timeout)
        if message is None:
            await asyncio.sleep(0)
            continue

        try:
            await service.process_job(message)
        except Exception as exc:
            logger.exception("Error processing job %s: %s", message.url_id, exc)