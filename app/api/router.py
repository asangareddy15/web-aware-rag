from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dto import InsertUrlRequest, QueryRequest, QueryResponse
from app.api.dependencies import get_ingestion_service, get_retrieval_service

from app.service.ingestion_service import IngestionService
from app.service.retrieval_service import RetrievalService

router = APIRouter(prefix="/api", tags=["ingestion"])


@router.post("/ingest-url", status_code=status.HTTP_202_ACCEPTED)
async def insert_url(
    payload: InsertUrlRequest,
    service: IngestionService = Depends(get_ingestion_service),
) -> None:
    if not payload.urls:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one URL is required")

    urls_as_str = [str(url) for url in payload.urls]
    await service.ingest_urls(urls_as_str)

    return

@router.post("/query")
async def query(
    payload: QueryRequest,
    retrieval_service: RetrievalService = Depends(get_retrieval_service),
) -> QueryResponse:
    if not payload.query:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Query cannot be empty")

    answer = await retrieval_service.process_query(payload.query)
    return QueryResponse(answer=answer)

