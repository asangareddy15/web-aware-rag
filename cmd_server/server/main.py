from __future__ import annotations

from fastapi import FastAPI

from app.api.router import router
from app.repository.repository import Repository
from app.service.ingestion_service import IngestionService
from app.service.retrieval_service import RetrievalService
from pkg.config.config import Settings
from pkg.embedding.client import VoyageEmbeddingClient
from pkg.llm.client import LLMClient
from pkg.postgres.client import PostgresClient
from pkg.redis.client import RedisQueue
from app.api.dependencies import set_ingestion_service, set_retrieval_service

settings = Settings()

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
llm_client = LLMClient(gemini_api_key=settings.gemini_api_key)
ingestion_service = IngestionService(repository=repository, embedding_client=embedding_client)
retrieval_service = RetrievalService(repository=repository, embedding_client=embedding_client, llm_client=llm_client)
set_ingestion_service(ingestion_service)
set_retrieval_service(retrieval_service)

app = FastAPI(title=settings.app_name)
app.include_router(router)


@app.on_event("startup")
async def startup_event() -> None:
    await postgres_client.connect()
    await postgres_client.create_tables()
    await redis_queue.connect()


@app.on_event("shutdown")
async def shutdown_event() -> None:
    await redis_queue.close()
    await postgres_client.disconnect()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="localhost", port=8000)
