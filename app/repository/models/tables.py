from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector

from pkg.postgres.client import Base


class UrlStatusEnum(str, Enum):
    PENDING = "PENDING"
    FETCHING = "FETCHING"
    CHUNKING = "CHUNKING"
    EMBEDDING = "EMBEDDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class UrlModel(Base):
    __tablename__ = "urls"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    url: Mapped[str] = mapped_column(String(2048), nullable=False, unique=True)
    status: Mapped[UrlStatusEnum] = mapped_column(SqlEnum(UrlStatusEnum, name="url_status"), nullable=False, default=UrlStatusEnum.PENDING)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    contents: Mapped[list["ContentModel"]] = relationship(back_populates="url", cascade="all, delete-orphan")
    chunks: Mapped[list["ChunkModel"]] = relationship(back_populates="url", cascade="all, delete-orphan")


class ContentModel(Base):
    __tablename__ = "contents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    url_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("urls.id", ondelete="CASCADE"), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    url: Mapped[UrlModel] = relationship(back_populates="contents")


class ChunkModel(Base):
    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    url_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("urls.id", ondelete="CASCADE"), nullable=False, index=True)
    content_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("contents.id", ondelete="CASCADE"), nullable=True)
    chunk_content: Mapped[str] = mapped_column(Text, nullable=False)
    is_embedded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    url: Mapped[UrlModel] = relationship(back_populates="chunks")
    content: Mapped[ContentModel | None] = relationship()
    embedding: Mapped[Optional["EmbeddingModel"]] = relationship(back_populates="chunk", cascade="all, delete-orphan", uselist=False)


class EmbeddingModel(Base):
    __tablename__ = "embeddings"
    __table_args__ = (
        UniqueConstraint("chunk_id", name="uq_embeddings_chunk"),
        CheckConstraint("vector IS NOT NULL", name="ck_embeddings_vector_not_null"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chunk_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chunks.id", ondelete="CASCADE"), nullable=False, index=True)
    vector: Mapped[list[float]] = mapped_column(Vector, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    chunk: Mapped["ChunkModel"] = relationship(back_populates="embedding")
