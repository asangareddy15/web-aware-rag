from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID


class UrlStatus(str, Enum):
    PENDING = "PENDING"
    FETCHING = "FETCHING"
    CHUNKING = "CHUNKING"
    EMBEDDING = "EMBEDDING"
    COMPLETED = "COMPLETED"


@dataclass(slots=True)
class UrlEntity:
    id: UUID
    url: str
    status: UrlStatus
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class ContentEntity:
    id: UUID
    url_id: UUID
    content: str
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class ChunkEntity:
    id: UUID
    url_id: UUID
    chunk_content: str
    is_embedded: bool
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class EmbeddingEntity:
    id: UUID
    chunk_id: UUID
    vector: list[float]
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class ChunkRetrieval:
    chunk: ChunkEntity
    url: str
    distance: float
