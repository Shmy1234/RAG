"""SQLAlchemy persistence for source documents and retrieval chunks."""

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.database.models.documents import DocumentChunk, SourceDocument
from ingest.chunking import ChunkRecord
from ingest.manifest import IngestDocument


def create_sessionmaker() -> sessionmaker[Session]:
    engine = create_engine(settings.sqlalchemy_database_url, pool_pre_ping=True)
    return sessionmaker(bind=engine, expire_on_commit=False)


def document_exists(session: Session, accession_number: str) -> bool:
    statement = select(SourceDocument.id).where(
        SourceDocument.accession_number == accession_number
    )
    return session.execute(statement).scalar_one_or_none() is not None


def source_document_values(document: IngestDocument, content: str) -> dict[str, Any]:
    return {
        "accession_number": document.accession_number,
        "ticker": document.ticker,
        "company_name": document.company_name,
        "filing_type": document.filing_type,
        "filing_date": document.filing_date,
        "fiscal_year": document.fiscal_year,
        "source_url": document.source_url,
        "content": content,
        "metadata": document.metadata,
    }


def source_document_kwargs(document: IngestDocument, content: str) -> dict[str, Any]:
    values = source_document_values(document, content)
    values["document_metadata"] = values.pop("metadata")
    return values


def replace_document(
    session: Session,
    document: IngestDocument,
    content: str,
) -> SourceDocument:
    existing = session.execute(
        select(SourceDocument).where(
            SourceDocument.accession_number == document.accession_number
        )
    ).scalar_one_or_none()
    if existing is not None:
        session.execute(delete(SourceDocument).where(SourceDocument.id == existing.id))
        session.flush()

    source_document = SourceDocument(**source_document_kwargs(document, content))
    session.add(source_document)
    session.flush()
    return source_document


def document_chunk_values(
    document_id: UUID,
    chunk: ChunkRecord,
    embedding: Sequence[float],
) -> dict[str, Any]:
    return {
        "document_id": document_id,
        "chunk_index": chunk.chunk_index,
        "page_number": chunk.page_number,
        "section": chunk.section[:255] if chunk.section else None,
        "text": chunk.text,
        "token_count": chunk.token_count,
        "chunk_metadata": chunk.metadata,
        "embedding": list(embedding),
    }


def insert_chunks(
    session: Session,
    source_document: SourceDocument,
    chunks: Sequence[ChunkRecord],
    embeddings: Sequence[Sequence[float]],
) -> None:
    if len(chunks) != len(embeddings):
        raise ValueError("Chunk and embedding counts must match")

    for chunk, embedding in zip(chunks, embeddings, strict=True):
        session.add(DocumentChunk(**document_chunk_values(source_document.id, chunk, embedding)))
