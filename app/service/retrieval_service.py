from __future__ import annotations

import json
import re
from typing import List, Tuple
from urllib.parse import urlparse

from loguru import logger

from app.repository.repository import Repository
from pkg.embedding.client import VoyageEmbeddingClient
from pkg.llm.client import LLMClient


MAX_CONTEXTS = 5
CANDIDATE_CHUNK_LIMIT = 12
MAX_CONTEXTS_PER_DOMAIN = 2
MIN_SIMILARITY = 0.2
STRATEGY_PROMPT = (
    "You decide whether to answer immediately or call a retrieval system. "
    "Respond ONLY as compact JSON with keys 'action', 'answer', and 'query'. "
    "Always populate 'query' with the best retrieval-ready reformulation of the user's request; it may match the original wording. "
    "Default to 'retrieve' unless the question is clearly answerable from evergreen, widely known facts (e.g. arithmetic, common definitions). "
    "Set 'action' to 'answer' only when you are certain no up-to-date or source-backed information is needed. "
    "Otherwise set 'action' to 'retrieve'. "
    "If action is 'answer', you may also include a concise response in 'answer', but 'query' must still be present. "
    "If action is 'retrieve', leave 'answer' empty. "
    "Do not include any text outside valid JSON."
)


class RetrievalService:
    """Handles semantic retrieval and LLM-backed question answering."""

    def __init__(self, repository: Repository, embedding_client: VoyageEmbeddingClient, llm_client: LLMClient) -> None:
        self._repository = repository
        self._embedding_client = embedding_client
        self._llm_client = llm_client

    async def process_query(self, query: str) -> str:
        cleaned_query = query.strip()
        if not cleaned_query:
            raise ValueError("Query must be a non-empty string")

        decision, reframed_query, direct_answer = await self._decide_strategy(cleaned_query)
        logger.debug("Strategy action=%s | reframed_query=%s", decision, reframed_query)
        query_text = reframed_query or cleaned_query

        query_vector = await self._embedding_client.embed_query(query_text)
        if not query_vector:
            logger.warning("Embedding client returned no vector for query")
            return "I could not find relevant information to answer that question."

        try:
            candidates = await self._repository.search_similar_chunks(query_vector, limit=CANDIDATE_CHUNK_LIMIT)
        except Exception as exc:
            logger.exception("Vector search failed: %s", exc)
            raise

        logger.debug(
            "Retrieved %s candidate chunks for query", len(candidates)
        )

        contexts: List[Tuple[str, float, str]] = []
        fallback_contexts: List[Tuple[str, float, str]] = []
        domain_counts: dict[str, int] = {}
        for candidate in candidates:
            snippet = re.sub(r"\s+", " ", candidate.chunk.chunk_content).strip()
            if not snippet:
                continue
            similarity = max(0.0, 1.0 - candidate.distance)
            fallback_contexts.append((snippet, similarity, candidate.url))
            if similarity < MIN_SIMILARITY:
                continue
            domain = urlparse(candidate.url).netloc
            count = domain_counts.get(domain, 0)
            if count >= MAX_CONTEXTS_PER_DOMAIN:
                continue
            domain_counts[domain] = count + 1
            contexts.append((snippet, similarity, candidate.url))
            if len(contexts) >= MAX_CONTEXTS:
                break

        if not contexts and fallback_contexts:
            fallback_contexts.sort(key=lambda item: item[1], reverse=True)
            contexts = fallback_contexts[:MAX_CONTEXTS]

        if not contexts:
            logger.info(
                "No usable contexts retrieved for query; candidate_count=%s",
                len(candidates),
            )
            if direct_answer:
                return direct_answer
            return "I could not find relevant information to answer that question."

        context_blocks = []
        for idx, (snippet, similarity, url) in enumerate(contexts, start=1):
            context_blocks.append(
                f"Context {idx} | similarity={similarity:.3f} | source={url}\n{snippet}"
            )
        context_section = "\n\n".join(context_blocks)

        prompt = (
            "You are a retrieval-augmented assistant. Use only the provided contexts to answer the user question. "
            "Cite the context number when relevant. If the answer cannot be derived from the contexts, state that "
            "the information is not available.\n\n"
            f"Question: {cleaned_query}\n\n"
            f"Contexts:\n{context_section}\n\n"
            "Answer:"
        )

        try:
            response = await self._llm_client.generate(prompt)
        except Exception as exc:
            logger.exception("LLM generation failed: %s", exc)
            raise

        return response.strip()

    async def _decide_strategy(self, query: str) -> Tuple[str, str, str | None]:
        prompt = f"{STRATEGY_PROMPT}\n\nUser question: {json.dumps(query)}"
        try:
            raw_decision = await self._llm_client.generate(prompt)
        except Exception as exc:
            logger.exception("Strategy decision failed: %s", exc)
            return "retrieve", query, None

        raw_text = raw_decision.strip()
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError:
            json_candidate = self._extract_json_object(raw_text)
            if json_candidate is None:
                logger.warning("Strategy response is not valid JSON: %s", raw_decision)
                return "retrieve", query, None
            try:
                payload = json.loads(json_candidate)
            except json.JSONDecodeError:
                logger.warning("Strategy response could not be parsed even after extraction: %s", raw_decision)
                return "retrieve", query, None

        action = str(payload.get("action", "retrieve")).strip().lower()

        answer = payload.get("answer", "")
        answer_text = answer.strip() if isinstance(answer, str) else ""

        reframed = payload.get("query", "")
        reframed_text = reframed.strip() if isinstance(reframed, str) else ""
        if not reframed_text:
            reframed_text = query

        return action or "retrieve", reframed_text, answer_text or None

    @staticmethod
    def _extract_json_object(text: str) -> str | None:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        return text[start : end + 1]
