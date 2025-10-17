from __future__ import annotations

import asyncio
from typing import List, Sequence

import voyageai
from loguru import logger


DEFAULT_MODEL_NAME = "voyage-context-3"
DEFAULT_OUTPUT_DIMENSION = 1024


class VoyageEmbeddingClient:
    """Wrapper around VoyageAI contextualized embeddings."""

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL_NAME,
        output_dimension: int = DEFAULT_OUTPUT_DIMENSION,
    ) -> None:
        self.client = voyageai.Client(api_key=api_key)
        self.model = model
        self.output_dimension = output_dimension

    async def embed_document(self, chunks: Sequence[str]) -> List[List[float]]:
        """Generate contextualized embeddings for ordered chunks of a document."""
        filtered = [chunk.strip() for chunk in chunks if chunk and chunk.strip()]
        if not filtered:
            return []
        return await asyncio.to_thread(self._embed_document_sync, filtered)

    def _embed_document_sync(self, chunks: Sequence[str]) -> List[List[float]]:
        logger.debug("Requesting Voyage embeddings for %s chunks", len(chunks))
        kwargs = {"model": self.model, "input_type": "document", "output_dimension": self.output_dimension}
        response = self.client.contextualized_embed(inputs=[list(chunks)], **kwargs)
        return [list(embedding) for embedding in response.results[0].embeddings]

    async def embed_query(self, query: str) -> List[float]:
        """Embed a single query string."""
        text = query.strip()
        if not text:
            return []
        embeddings = await asyncio.to_thread(self._embed_query_sync, text)
        return embeddings

    def _embed_query_sync(self, query: str) -> List[float]:
        kwargs = {"model": self.model, "input_type": "query", "output_dimension": self.output_dimension}
        response = self.client.contextualized_embed(inputs=[[query]], **kwargs)
        return list(response.results[0].embeddings[0])
