from __future__ import annotations

import re
from typing import List, Tuple

from loguru import logger

from app.repository.repository import Repository
from pkg.embedding.client import VoyageEmbeddingClient



class RetrievalService:
    """Handles semantic retrieval and LLM-backed question answering."""

    def __init__(self, repository: Repository, embedding_client: VoyageEmbeddingClient) -> None:
        self._repository = repository
        self._embedding_client = embedding_client

    async def process_query(self, query: str) -> str:
        pass
