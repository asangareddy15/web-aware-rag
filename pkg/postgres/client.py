from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool, AsyncAdaptedQueuePool
from sqlalchemy import text, event
from loguru import logger

# Base class for all SQLAlchemy models
Base = declarative_base()


class PostgresClient:
    """Async PostgreSQL client with pgvector extension support"""

    def __init__(self, user: str, password: str, host: str, port: int, database: str, pool_size: int = 10):

        self.user = user
        self.password = password
        self.host = host
        self.port = port
        self.database = database

        # Build connection URL for asyncpg
        self.database_url = (
            f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"
        )

        self._engine = None
        self._session_factory: Optional[async_sessionmaker] = None
        self.pool_size = pool_size

        logger.info(f"PostgreSQL client initialized for {host}:{port}/{database}")

    async def connect(self) -> None:

        if self._engine is not None:
            logger.warning("PostgreSQL client already connected")
            return

        try:
            # Create async engine
            self._engine = create_async_engine(
                self.database_url,
                poolclass=AsyncAdaptedQueuePool,
                pool_size=self.pool_size,
                pool_pre_ping=True,
                pool_recycle=3600,  # Recycle connections after 1 hour
            )

            # Create session factory
            self._session_factory = async_sessionmaker(
                self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autocommit=False,
                autoflush=False,
            )

            # Initialize pgvector extension
            await self._init_pgvector()

            logger.info("PostgreSQL connection established successfully")


        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise

    async def _init_pgvector(self) -> None:
        """Initialize pgvector extension if not already present."""
        try:
            async with self._engine.begin() as conn:
                # Create pgvector extension
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                logger.info("pgvector extension initialized")
        except Exception as e:
            logger.error(f"Failed to initialize pgvector extension: {e}")
            raise

    async def disconnect(self) -> None:
        """Close all database connections."""
        if self._engine is None:
            logger.warning("PostgreSQL client not connected")
            return

        try:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
            logger.info("PostgreSQL connection closed")
        except Exception as e:
            logger.error(f"Error closing PostgreSQL connection: {e}")
            raise

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        if self._session_factory is None:
            raise RuntimeError("PostgreSQL client not connected. Call connect() first.")

        session: AsyncSession = self._session_factory()
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Session error, rolling back: {e}")
            raise
        finally:
            await session.close()

    async def create_tables(self) -> None:

        if self._engine is None:
            raise RuntimeError("PostgreSQL client not connected")

        try:
            async with self._engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Failed to create tables: {e}")
            raise


    async def health_check(self) -> bool:

        if self._engine is None:
            return False

        try:
            async with self._engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    async def execute_raw(self, query: str, params: Optional[dict] = None) -> None:
        """
        Execute raw SQL query.

        Args:
            query: SQL query string
            params: Optional query parameters
        """
        async with self.get_session() as session:
            await session.execute(text(query), params or {})

    @property
    def engine(self):
        """Get the SQLAlchemy engine."""
        if self._engine is None:
            raise RuntimeError("PostgreSQL client not connected")
        return self._engine

    @property
    def session_factory(self) -> async_sessionmaker:
        """Get the session factory."""
        if self._session_factory is None:
            raise RuntimeError("PostgreSQL client not connected")
        return self._session_factory


