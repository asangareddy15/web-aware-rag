from __future__ import annotations

from typing import Optional

from app.service.ingestion_service import IngestionService
from app.service.retrieval_service import RetrievalService

_ingestion_service: Optional[IngestionService] = None
_retrieval_service: Optional[RetrievalService] = None


def set_ingestion_service(service: IngestionService) -> None:
    global _ingestion_service
    _ingestion_service = service


def get_ingestion_service() -> IngestionService:
    if _ingestion_service is None:
        raise RuntimeError("Ingestion service not initialised")
    return _ingestion_service

def set_retrieval_service(service: RetrievalService) -> None:
    global _retrieval_service
    _retrieval_service = service

def get_retrieval_service() -> RetrievalService:
    if _retrieval_service is None:
        raise RuntimeError("Retrieval service not initialised")
    return _retrieval_service
