from __future__ import annotations

from datetime import datetime, timezone
from typing import List
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl

from app.entities.entity import UrlStatus


class InsertUrlRequest(BaseModel):
    urls: List[HttpUrl]


class UrlSubmission(BaseModel):
    id: UUID
    url: HttpUrl
    status: UrlStatus


class InsertUrlResponse(BaseModel):
    urls: List[UrlSubmission]
    accepted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class IngestionMessage(BaseModel):
    url_id: UUID
    url: HttpUrl
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class QueryRequest(BaseModel):
    query: str

class QueryResponse(BaseModel):
    answer: str