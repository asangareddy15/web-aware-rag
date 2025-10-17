from __future__ import annotations

import json
from typing import Any, Optional

from loguru import logger
from redis.asyncio import Redis


class RedisQueue:
    """Thin async wrapper around Redis lists for queue semantics."""

    def __init__(self, host: str, port: int, queue_name: str = "ingestion_queue", db: int = 0):
        self._host = host
        self._port = port
        self._db = db
        self._queue_name = queue_name
        self._client: Optional[Redis] = None

    async def connect(self) -> None:
        if self._client is not None:
            logger.warning("Redis client already connected")
            return

        self._client = Redis(host=self._host, port=self._port, db=self._db, decode_responses=True)
        await self._client.ping()
        logger.info("Connected to Redis at {host}:{port}", host=self._host, port=self._port)

    async def close(self) -> None:
        if self._client is None:
            return

        await self._client.close()
        await self._client.connection_pool.disconnect()
        self._client = None
        logger.info("Redis connection closed")

    async def enqueue(self, payload: Any) -> None:
        if self._client is None:
            raise RuntimeError("Redis client not connected")

        data = payload if isinstance(payload, str) else json.dumps(payload)
        await self._client.rpush(self._queue_name, data)

    async def dequeue(self, timeout: int = 0) -> Optional[str]:
        if self._client is None:
            raise RuntimeError("Redis client not connected")

        result = await self._client.blpop(self._queue_name, timeout=timeout)
        if result is None:
            return None

        _, data = result
        return data

    async def length(self) -> int:
        if self._client is None:
            raise RuntimeError("Redis client not connected")
        return await self._client.llen(self._queue_name)

    @property
    def queue_name(self) -> str:
        return self._queue_name
