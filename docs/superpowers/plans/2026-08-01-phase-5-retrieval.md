# Phase 5 Retrieval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the retrieval pipeline so a user question returns ranked, relevant SEC filing passages from `document_chunks`.

**Architecture:** Runtime retrieval uses the same hybrid pattern as Dave Ebbelaar's cookbook: run dense retrieval and sparse retrieval independently, fuse by rank with Reciprocal Rank Fusion, then return the top passages. In this repo, dense retrieval is Supabase Postgres `pgvector`, sparse retrieval is Postgres full-text search over the generated `search_vector`, and the retriever returns typed passage objects that Phase 6 PydanticAI tools can expose as `search_filings`, `read_chunk`, and `read_surrounding_chunks`.

**Tech Stack:** Python 3.12, FastAPI backend package layout, Pydantic v2 models, SQLAlchemy 2.0, pgvector SQLAlchemy comparator, Postgres full-text search, OpenAI async embeddings API, pytest.

## Global Constraints

- Stack is locked: FastAPI, Supabase Postgres, pgvector, Postgres full-text search, OpenAI, and PydanticAI.
- Do not add a BM25 dependency; sparse retrieval must use Postgres full-text search over `document_chunks.search_vector`.
- Do not add a reranker in Phase 5; the cookbook reranker is useful later, but Phase 5 scope is semantic + full-text + RRF + neighboring chunks.
- Use `app.config.settings` for OpenAI embedding model and dimensions; do not call `os.getenv` in app code.
- Query embeddings must use `settings.OPENAI_EMBEDDING_MODEL` and `settings.OPENAI_EMBEDDING_DIMENSIONS`, matching stored `vector(1536)` rows.
- Request-path code must be async at network boundaries; OpenAI query embedding uses `AsyncOpenAI`.
- Unit tests must not call OpenAI or a real database.
- Integration tests that hit Supabase stay behind `@pytest.mark.integration` and skip unless explicitly enabled.
- Retrieval results must include enough source metadata for citation UI and Phase 6 grounding: chunk id, document id, ticker, company name, filing type, filing date, fiscal year, page number, section, source URL, text, ranks, and scores.

---

## Source Notes

- `docs/todos.md` Phase 5 asks for `retrieval/queries.py`, semantic search, full-text search, `retrieval/fusion.py`, `retrieval/retriever.py`, unit tests, optional integration test, and manual/scripted verification.
- `docs/architecture.md` defines the target retrieval strategy: embed query, run pgvector, run full-text search, fuse with RRF, fetch selected chunks plus neighbors.
- Dave Ebbelaar's `knowledge/hybrid-retrieval/utils/retrievers.py` separates dense and sparse retrievers behind identical `search(query, k)` methods.
- Dave Ebbelaar's `knowledge/hybrid-retrieval/utils/fusion.py` fuses ranked document id lists with `1 / (k + rank)` and intentionally combines ranks rather than incomparable raw scores.
- Dave Ebbelaar's PydanticAI examples use typed dependencies, typed outputs, bounded tool outputs, and agent-readable tool errors. Phase 5 should produce typed retrieval objects so Phase 6 can expose them cleanly through PydanticAI tools.
- Current PydanticAI docs still support `Agent(..., deps_type=..., output_type=...)`, `RunContext[Deps]`, `@agent.tool`, and `UsageLimits`.
- The installed `pgvector.sqlalchemy.Vector` comparator exposes `cosine_distance`, so semantic search can use SQLAlchemy expressions instead of formatting vector literals by hand.

## File Structure

- Create `backend/app/retrieval/schemas.py`: Pydantic models for filters, chunk references, ranked results, fused results, and returned source passages.
- Create `backend/app/retrieval/embeddings.py`: async OpenAI query embedding boundary with dependency-injection-friendly protocol.
- Create `backend/app/retrieval/queries.py`: SQLAlchemy query helpers for pgvector semantic search, Postgres full-text search, chunk lookup, and neighboring chunk lookup.
- Create `backend/app/retrieval/fusion.py`: RRF implementation over ranked chunk lists.
- Create `backend/app/retrieval/retriever.py`: high-level `DocumentRetriever` that embeds a user query, runs both retrieval queries, fuses candidates, and attaches neighbor chunks.
- Modify `backend/app/retrieval/__init__.py`: export public retrieval types and `DocumentRetriever`.
- Create `backend/tests/retrieval/test_schemas.py`: focused tests for filter normalization and result shaping.
- Create `backend/tests/retrieval/test_embeddings.py`: fake-client unit tests for query embedding.
- Create `backend/tests/retrieval/test_queries.py`: SQL assembly and row-mapping tests without a real database.
- Create `backend/tests/retrieval/test_fusion.py`: RRF ranking, score merging, and stable tie behavior.
- Create `backend/tests/retrieval/test_retriever.py`: orchestration tests with fake embedder and monkeypatched query functions.
- Create `backend/tests/retrieval/test_integration.py`: optional Supabase integration test against an ingested corpus.
- Modify `docs/todos.md`: mark Phase 5 items complete only after implementation and verification.

## Task 1: Retrieval Schemas

**Files:**
- Create: `backend/app/retrieval/schemas.py`
- Modify: `backend/app/retrieval/__init__.py`
- Test: `backend/tests/retrieval/test_schemas.py`

**Interfaces:**
- Produces:
  - `RetrievalFilters(tickers: tuple[str, ...] = (), filing_types: tuple[str, ...] = (), fiscal_years: tuple[int, ...] = ())`
  - `ChunkReference` with chunk/document metadata and text.
  - `RankedChunk(chunk: ChunkReference, rank: int, score: float, source: Literal["semantic", "full_text"])`
  - `FusedChunk(chunk: ChunkReference, rrf_score: float, semantic_rank: int | None, full_text_rank: int | None, semantic_score: float | None, full_text_score: float | None)`
  - `SourcePassage(center: FusedChunk, previous_chunks: list[ChunkReference], next_chunks: list[ChunkReference])`

- [ ] **Step 1: Write failing schema tests**

```python
from datetime import date
from uuid import UUID

from app.retrieval.schemas import ChunkReference, RetrievalFilters


def test_retrieval_filters_normalize_uppercase_values():
    filters = RetrievalFilters(
        tickers=("aapl", " msft "),
        filing_types=("10-k",),
        fiscal_years=(2025, 2021),
    )

    assert filters.tickers == ("AAPL", "MSFT")
    assert filters.filing_types == ("10-K",)
    assert filters.fiscal_years == (2025, 2021)


def test_chunk_reference_carries_citation_metadata():
    chunk = ChunkReference(
        chunk_id=UUID("00000000-0000-0000-0000-000000000001"),
        document_id=UUID("00000000-0000-0000-0000-000000000002"),
        chunk_index=7,
        text="Net sales increased year over year.",
        page_number=42,
        section="Management's Discussion and Analysis",
        ticker="AAPL",
        company_name="Apple Inc.",
        filing_type="10-K",
        filing_date=date(2025, 10, 31),
        fiscal_year=2025,
        accession_number="0000320193-25-000079",
        source_url="https://www.sec.gov/example",
    )

    assert chunk.citation_label == "AAPL 10-K 2025"
    assert chunk.location_label == "page 42, Management's Discussion and Analysis"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/retrieval/test_schemas.py -q`

Expected: FAIL because `app.retrieval.schemas` does not exist.

- [ ] **Step 3: Implement schemas**

Use Pydantic models because Phase 6 PydanticAI tools can return them directly without custom JSON conversion.

```python
from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class RetrievalFilters(BaseModel):
    tickers: tuple[str, ...] = ()
    filing_types: tuple[str, ...] = ()
    fiscal_years: tuple[int, ...] = ()

    @field_validator("tickers", "filing_types", mode="before")
    @classmethod
    def normalize_strings(cls, value: object) -> tuple[str, ...]:
        if value is None:
            return ()
        return tuple(str(item).strip().upper() for item in value if str(item).strip())


class ChunkReference(BaseModel):
    chunk_id: UUID
    document_id: UUID
    chunk_index: int
    text: str
    page_number: int | None
    section: str | None
    ticker: str
    company_name: str
    filing_type: str
    filing_date: date
    fiscal_year: int
    accession_number: str
    source_url: str

    @property
    def citation_label(self) -> str:
        return f"{self.ticker} {self.filing_type} {self.fiscal_year}"

    @property
    def location_label(self) -> str:
        parts = []
        if self.page_number is not None:
            parts.append(f"page {self.page_number}")
        if self.section:
            parts.append(self.section)
        return ", ".join(parts) or "unknown location"


class RankedChunk(BaseModel):
    chunk: ChunkReference
    rank: int = Field(ge=1)
    score: float
    source: Literal["semantic", "full_text"]


class FusedChunk(BaseModel):
    chunk: ChunkReference
    rrf_score: float
    semantic_rank: int | None = None
    full_text_rank: int | None = None
    semantic_score: float | None = None
    full_text_score: float | None = None


class SourcePassage(BaseModel):
    center: FusedChunk
    previous_chunks: list[ChunkReference] = Field(default_factory=list)
    next_chunks: list[ChunkReference] = Field(default_factory=list)
```

Export these types from `backend/app/retrieval/__init__.py`.

- [ ] **Step 4: Run schema tests**

Run: `cd backend && uv run pytest tests/retrieval/test_schemas.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/retrieval/__init__.py backend/app/retrieval/schemas.py backend/tests/retrieval/test_schemas.py
git commit -m "feat: add retrieval result schemas"
```

## Task 2: Query Embedding Boundary

**Files:**
- Create: `backend/app/retrieval/embeddings.py`
- Test: `backend/tests/retrieval/test_embeddings.py`

**Interfaces:**
- Produces:
  - `QueryEmbedder` protocol with `embed_query(self, query: str) -> list[float]`
  - `OpenAIQueryEmbedder(client: AsyncOpenAI | None = None)`

- [ ] **Step 1: Write failing embedding tests**

```python
import asyncio

import pytest

from app.retrieval.embeddings import OpenAIQueryEmbedder


class FakeEmbedding:
    embedding = [0.1, 0.2, 0.3]


class FakeResponse:
    data = [FakeEmbedding()]


class FakeEmbeddingsClient:
    def __init__(self):
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return FakeResponse()


class FakeClient:
    def __init__(self):
        self.embeddings = FakeEmbeddingsClient()


def test_embed_query_uses_configured_model_and_dimensions(monkeypatch):
    monkeypatch.setattr("app.retrieval.embeddings.settings.OPENAI_EMBEDDING_DIMENSIONS", 3)
    fake_client = FakeClient()
    embedder = OpenAIQueryEmbedder(client=fake_client)

    vector = asyncio.run(embedder.embed_query("  Apple revenue mix  "))

    assert vector == [0.1, 0.2, 0.3]
    assert fake_client.embeddings.calls == [
        {
            "model": "text-embedding-3-small",
            "input": ["Apple revenue mix"],
            "dimensions": 3,
            "encoding_format": "float",
        }
    ]


def test_embed_query_rejects_blank_query():
    embedder = OpenAIQueryEmbedder(client=FakeClient())

    with pytest.raises(ValueError, match="query"):
        asyncio.run(embedder.embed_query("   "))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/retrieval/test_embeddings.py -q`

Expected: FAIL because `app.retrieval.embeddings` does not exist.

- [ ] **Step 3: Implement the async embedder**

```python
from typing import Protocol

from openai import AsyncOpenAI

from app.config import settings


class QueryEmbedder(Protocol):
    async def embed_query(self, query: str) -> list[float]:
        """Return an embedding vector for a user query."""


class OpenAIQueryEmbedder:
    def __init__(self, client: AsyncOpenAI | None = None) -> None:
        self._client = client or AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def embed_query(self, query: str) -> list[float]:
        normalized = query.strip()
        if not normalized:
            raise ValueError("query must not be blank")

        response = await self._client.embeddings.create(
            model=settings.OPENAI_EMBEDDING_MODEL,
            input=[normalized],
            dimensions=settings.OPENAI_EMBEDDING_DIMENSIONS,
            encoding_format="float",
        )
        vector = list(response.data[0].embedding)
        if len(vector) != settings.OPENAI_EMBEDDING_DIMENSIONS:
            raise ValueError(
                f"query embedding dimension {len(vector)} did not match "
                f"{settings.OPENAI_EMBEDDING_DIMENSIONS}"
            )
        return vector
```

- [ ] **Step 4: Run embedding tests**

Run: `cd backend && uv run pytest tests/retrieval/test_embeddings.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/retrieval/embeddings.py backend/tests/retrieval/test_embeddings.py
git commit -m "feat: add retrieval query embedding"
```

## Task 3: Semantic And Full-Text Query Helpers

**Files:**
- Create: `backend/app/retrieval/queries.py`
- Test: `backend/tests/retrieval/test_queries.py`

**Interfaces:**
- Consumes: `RetrievalFilters`, `ChunkReference`, `RankedChunk`
- Produces:
  - `semantic_search(session: Session, query_embedding: Sequence[float], limit: int, filters: RetrievalFilters) -> list[RankedChunk]`
  - `full_text_search(session: Session, query: str, limit: int, filters: RetrievalFilters) -> list[RankedChunk]`
  - `read_chunk(session: Session, chunk_id: UUID) -> ChunkReference | None`
  - `read_surrounding_chunks(session: Session, chunk: ChunkReference, window: int) -> tuple[list[ChunkReference], list[ChunkReference]]`

- [ ] **Step 1: Write failing row-mapping tests**

```python
from datetime import date
from types import SimpleNamespace
from uuid import UUID

from app.retrieval.queries import chunk_reference_from_row, ranked_chunk_from_row


def row(score=0.42):
    return SimpleNamespace(
        chunk_id=UUID("00000000-0000-0000-0000-000000000001"),
        document_id=UUID("00000000-0000-0000-0000-000000000002"),
        chunk_index=3,
        text="Revenue from Services increased.",
        page_number=12,
        section="Results of Operations",
        ticker="AAPL",
        company_name="Apple Inc.",
        filing_type="10-K",
        filing_date=date(2025, 10, 31),
        fiscal_year=2025,
        accession_number="0000320193-25-000079",
        source_url="https://www.sec.gov/example",
        score=score,
    )


def test_ranked_chunk_from_row_maps_database_fields():
    result = ranked_chunk_from_row(row(), rank=2, source="semantic")

    assert result.rank == 2
    assert result.score == 0.42
    assert result.source == "semantic"
    assert result.chunk.ticker == "AAPL"
    assert result.chunk.chunk_index == 3
```

- [ ] **Step 2: Write failing SQL assembly tests**

```python
from sqlalchemy.dialects import postgresql

from app.retrieval.queries import build_full_text_statement, build_semantic_statement
from app.retrieval.schemas import RetrievalFilters


def compiled(statement) -> str:
    return str(statement.compile(dialect=postgresql.dialect()))


def test_semantic_statement_uses_pgvector_cosine_distance_and_filters():
    statement = build_semantic_statement(
        query_embedding=[0.1, 0.2, 0.3],
        limit=25,
        filters=RetrievalFilters(tickers=("aapl",), fiscal_years=(2025,)),
    )

    sql = compiled(statement)

    assert "document_chunks.embedding <=>" in sql
    assert "source_documents.ticker" in sql
    assert "source_documents.fiscal_year" in sql
    assert "LIMIT" in sql


def test_full_text_statement_uses_websearch_to_tsquery_and_rank():
    statement = build_full_text_statement(
        query="Apple Services revenue",
        limit=25,
        filters=RetrievalFilters(filing_types=("10-k",)),
    )

    sql = compiled(statement)

    assert "websearch_to_tsquery" in sql
    assert "@@" in sql
    assert "ts_rank_cd" in sql
    assert "source_documents.filing_type" in sql
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/retrieval/test_queries.py -q`

Expected: FAIL because `app.retrieval.queries` does not exist.

- [ ] **Step 4: Implement shared projection, filters, and row mapping**

```python
from collections.abc import Sequence
from typing import Literal
from uuid import UUID

from sqlalchemy import Select, desc, func, select
from sqlalchemy.orm import Session

from app.database.models.documents import DocumentChunk, SourceDocument
from app.retrieval.schemas import ChunkReference, RankedChunk, RetrievalFilters


def _base_columns():
    return (
        DocumentChunk.id.label("chunk_id"),
        DocumentChunk.document_id.label("document_id"),
        DocumentChunk.chunk_index,
        DocumentChunk.text,
        DocumentChunk.page_number,
        DocumentChunk.section,
        SourceDocument.ticker,
        SourceDocument.company_name,
        SourceDocument.filing_type,
        SourceDocument.filing_date,
        SourceDocument.fiscal_year,
        SourceDocument.accession_number,
        SourceDocument.source_url,
    )


def apply_filters(statement: Select, filters: RetrievalFilters) -> Select:
    if filters.tickers:
        statement = statement.where(SourceDocument.ticker.in_(filters.tickers))
    if filters.filing_types:
        statement = statement.where(SourceDocument.filing_type.in_(filters.filing_types))
    if filters.fiscal_years:
        statement = statement.where(SourceDocument.fiscal_year.in_(filters.fiscal_years))
    return statement


def chunk_reference_from_row(row) -> ChunkReference:
    return ChunkReference(
        chunk_id=row.chunk_id,
        document_id=row.document_id,
        chunk_index=row.chunk_index,
        text=row.text,
        page_number=row.page_number,
        section=row.section,
        ticker=row.ticker,
        company_name=row.company_name,
        filing_type=row.filing_type,
        filing_date=row.filing_date,
        fiscal_year=row.fiscal_year,
        accession_number=row.accession_number,
        source_url=row.source_url,
    )


def ranked_chunk_from_row(
    row,
    *,
    rank: int,
    source: Literal["semantic", "full_text"],
) -> RankedChunk:
    return RankedChunk(
        chunk=chunk_reference_from_row(row),
        rank=rank,
        score=float(row.score),
        source=source,
    )
```

- [ ] **Step 5: Implement pgvector semantic query**

```python
def build_semantic_statement(
    query_embedding: Sequence[float],
    *,
    limit: int,
    filters: RetrievalFilters,
) -> Select:
    distance = DocumentChunk.embedding.cosine_distance(list(query_embedding))
    statement = (
        select(*_base_columns(), (1 - distance).label("score"))
        .join(SourceDocument, SourceDocument.id == DocumentChunk.document_id)
        .where(DocumentChunk.embedding.is_not(None))
        .order_by(distance)
        .limit(limit)
    )
    return apply_filters(statement, filters)


def semantic_search(
    session: Session,
    query_embedding: Sequence[float],
    *,
    limit: int,
    filters: RetrievalFilters,
) -> list[RankedChunk]:
    rows = session.execute(
        build_semantic_statement(query_embedding, limit=limit, filters=filters)
    ).all()
    return [
        ranked_chunk_from_row(row, rank=rank, source="semantic")
        for rank, row in enumerate(rows, start=1)
    ]
```

- [ ] **Step 6: Implement Postgres full-text query**

```python
def build_full_text_statement(
    query: str,
    *,
    limit: int,
    filters: RetrievalFilters,
) -> Select:
    ts_query = func.websearch_to_tsquery("english", query)
    rank = func.ts_rank_cd(DocumentChunk.search_vector, ts_query)
    statement = (
        select(*_base_columns(), rank.label("score"))
        .join(SourceDocument, SourceDocument.id == DocumentChunk.document_id)
        .where(DocumentChunk.search_vector.op("@@")(ts_query))
        .order_by(desc(rank))
        .limit(limit)
    )
    return apply_filters(statement, filters)


def full_text_search(
    session: Session,
    query: str,
    *,
    limit: int,
    filters: RetrievalFilters,
) -> list[RankedChunk]:
    normalized = query.strip()
    if not normalized:
        return []
    rows = session.execute(
        build_full_text_statement(normalized, limit=limit, filters=filters)
    ).all()
    return [
        ranked_chunk_from_row(row, rank=rank, source="full_text")
        for rank, row in enumerate(rows, start=1)
    ]
```

- [ ] **Step 7: Implement chunk lookup and neighbor lookup**

```python
def build_read_chunk_statement(chunk_id: UUID) -> Select:
    return (
        select(*_base_columns())
        .join(SourceDocument, SourceDocument.id == DocumentChunk.document_id)
        .where(DocumentChunk.id == chunk_id)
    )


def read_chunk(session: Session, chunk_id: UUID) -> ChunkReference | None:
    row = session.execute(build_read_chunk_statement(chunk_id)).one_or_none()
    return chunk_reference_from_row(row) if row is not None else None


def read_surrounding_chunks(
    session: Session,
    chunk: ChunkReference,
    *,
    window: int,
) -> tuple[list[ChunkReference], list[ChunkReference]]:
    if window < 1:
        return [], []
    statement = (
        select(*_base_columns())
        .join(SourceDocument, SourceDocument.id == DocumentChunk.document_id)
        .where(DocumentChunk.document_id == chunk.document_id)
        .where(DocumentChunk.chunk_index >= chunk.chunk_index - window)
        .where(DocumentChunk.chunk_index <= chunk.chunk_index + window)
        .where(DocumentChunk.id != chunk.chunk_id)
        .order_by(DocumentChunk.chunk_index)
    )
    neighbors = [chunk_reference_from_row(row) for row in session.execute(statement).all()]
    previous = [item for item in neighbors if item.chunk_index < chunk.chunk_index]
    next_chunks = [item for item in neighbors if item.chunk_index > chunk.chunk_index]
    return previous, next_chunks
```

- [ ] **Step 8: Run query tests**

Run: `cd backend && uv run pytest tests/retrieval/test_queries.py -q`

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add backend/app/retrieval/queries.py backend/tests/retrieval/test_queries.py
git commit -m "feat: add hybrid retrieval queries"
```

## Task 4: Reciprocal Rank Fusion

**Files:**
- Create: `backend/app/retrieval/fusion.py`
- Test: `backend/tests/retrieval/test_fusion.py`

**Interfaces:**
- Consumes: `RankedChunk`
- Produces:
  - `reciprocal_rank_fusion(rankings: Sequence[Sequence[RankedChunk]], k: int = 60) -> list[FusedChunk]`

- [ ] **Step 1: Write failing fusion tests**

```python
from datetime import date
from uuid import UUID

from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.schemas import ChunkReference, RankedChunk


def chunk(number: int) -> ChunkReference:
    return ChunkReference(
        chunk_id=UUID(f"00000000-0000-0000-0000-{number:012d}"),
        document_id=UUID("00000000-0000-0000-0000-999999999999"),
        chunk_index=number,
        text=f"chunk {number}",
        page_number=None,
        section=None,
        ticker="AAPL",
        company_name="Apple Inc.",
        filing_type="10-K",
        filing_date=date(2025, 10, 31),
        fiscal_year=2025,
        accession_number="0000320193-25-000079",
        source_url="https://www.sec.gov/example",
    )


def ranked(number: int, rank: int, source: str, score: float) -> RankedChunk:
    return RankedChunk(chunk=chunk(number), rank=rank, source=source, score=score)


def test_rrf_rewards_chunks_found_by_both_retrievers():
    fused = reciprocal_rank_fusion(
        [
            [ranked(1, 1, "semantic", 0.9), ranked(2, 2, "semantic", 0.8)],
            [ranked(2, 1, "full_text", 3.0), ranked(3, 2, "full_text", 2.0)],
        ],
        k=60,
    )

    assert [item.chunk.chunk_id for item in fused][:2] == [
        UUID("00000000-0000-0000-0000-000000000002"),
        UUID("00000000-0000-0000-0000-000000000001"),
    ]
    assert fused[0].semantic_rank == 2
    assert fused[0].full_text_rank == 1
    assert fused[0].semantic_score == 0.8
    assert fused[0].full_text_score == 3.0


def test_rrf_rejects_non_positive_k():
    try:
        reciprocal_rank_fusion([], k=0)
    except ValueError as exc:
        assert "k" in str(exc)
    else:
        raise AssertionError("expected ValueError")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/retrieval/test_fusion.py -q`

Expected: FAIL because `app.retrieval.fusion` does not exist.

- [ ] **Step 3: Implement fusion**

Follow the cookbook pattern: fuse ranks, not scores. Use first-seen order as the final deterministic tie-breaker so tests and production logs are stable.

```python
from collections.abc import Sequence

from app.retrieval.schemas import FusedChunk, RankedChunk


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[RankedChunk]],
    *,
    k: int = 60,
) -> list[FusedChunk]:
    if k <= 0:
        raise ValueError("k must be greater than zero")

    fused: dict[str, FusedChunk] = {}
    first_seen: dict[str, int] = {}
    seen_counter = 0

    for ranking in rankings:
        for item in ranking:
            key = str(item.chunk.chunk_id)
            if key not in fused:
                seen_counter += 1
                first_seen[key] = seen_counter
                fused[key] = FusedChunk(chunk=item.chunk, rrf_score=0.0)

            current = fused[key]
            current.rrf_score += 1.0 / (k + item.rank)
            if item.source == "semantic":
                current.semantic_rank = item.rank
                current.semantic_score = item.score
            else:
                current.full_text_rank = item.rank
                current.full_text_score = item.score

    return sorted(
        fused.values(),
        key=lambda item: (-item.rrf_score, first_seen[str(item.chunk.chunk_id)]),
    )
```

- [ ] **Step 4: Run fusion tests**

Run: `cd backend && uv run pytest tests/retrieval/test_fusion.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/retrieval/fusion.py backend/tests/retrieval/test_fusion.py
git commit -m "feat: add reciprocal rank fusion"
```

## Task 5: Document Retriever Orchestration

**Files:**
- Create: `backend/app/retrieval/retriever.py`
- Modify: `backend/app/retrieval/__init__.py`
- Test: `backend/tests/retrieval/test_retriever.py`

**Interfaces:**
- Consumes:
  - `QueryEmbedder.embed_query(query: str) -> list[float]`
  - `semantic_search(...) -> list[RankedChunk]`
  - `full_text_search(...) -> list[RankedChunk]`
  - `read_surrounding_chunks(...) -> tuple[list[ChunkReference], list[ChunkReference]]`
  - `reciprocal_rank_fusion(...) -> list[FusedChunk]`
- Produces:
  - `DocumentRetriever(session_factory: Callable[[], AbstractContextManager[Session]], embedder: QueryEmbedder | None = None)`
  - `DocumentRetriever.retrieve(query: str, top_k: int = 10, candidate_k: int = 50, filters: RetrievalFilters | None = None, neighbor_window: int = 1) -> list[SourcePassage]`

- [ ] **Step 1: Write failing orchestration test**

```python
import asyncio
from contextlib import contextmanager
from datetime import date
from uuid import UUID

from app.retrieval.retriever import DocumentRetriever
from app.retrieval.schemas import ChunkReference, RankedChunk, RetrievalFilters


class FakeEmbedder:
    async def embed_query(self, query: str) -> list[float]:
        assert query == "Apple revenue mix"
        return [0.1, 0.2, 0.3]


@contextmanager
def fake_session_factory():
    yield object()


def make_chunk(number: int) -> ChunkReference:
    return ChunkReference(
        chunk_id=UUID(f"00000000-0000-0000-0000-{number:012d}"),
        document_id=UUID("00000000-0000-0000-0000-999999999999"),
        chunk_index=number,
        text=f"chunk {number}",
        page_number=number,
        section="Results of Operations",
        ticker="AAPL",
        company_name="Apple Inc.",
        filing_type="10-K",
        filing_date=date(2025, 10, 31),
        fiscal_year=2025,
        accession_number="0000320193-25-000079",
        source_url="https://www.sec.gov/example",
    )


def test_retrieve_runs_both_queries_fuses_and_attaches_neighbors(monkeypatch):
    calls = []

    def fake_semantic_search(session, query_embedding, *, limit, filters):
        calls.append(("semantic", query_embedding, limit, filters))
        return [RankedChunk(chunk=make_chunk(1), rank=1, score=0.9, source="semantic")]

    def fake_full_text_search(session, query, *, limit, filters):
        calls.append(("full_text", query, limit, filters))
        return [RankedChunk(chunk=make_chunk(1), rank=1, score=2.5, source="full_text")]

    def fake_neighbors(session, chunk, *, window):
        assert window == 1
        return [make_chunk(0)], [make_chunk(2)]

    monkeypatch.setattr("app.retrieval.retriever.semantic_search", fake_semantic_search)
    monkeypatch.setattr("app.retrieval.retriever.full_text_search", fake_full_text_search)
    monkeypatch.setattr("app.retrieval.retriever.read_surrounding_chunks", fake_neighbors)

    retriever = DocumentRetriever(session_factory=fake_session_factory, embedder=FakeEmbedder())
    passages = asyncio.run(
        retriever.retrieve(
            "Apple revenue mix",
            top_k=5,
            candidate_k=20,
            filters=RetrievalFilters(tickers=("aapl",)),
        )
    )

    assert len(passages) == 1
    assert passages[0].center.semantic_rank == 1
    assert passages[0].center.full_text_rank == 1
    assert passages[0].previous_chunks[0].chunk_index == 0
    assert passages[0].next_chunks[0].chunk_index == 2
    assert calls[0][0] == "semantic"
    assert calls[1][0] == "full_text"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/retrieval/test_retriever.py -q`

Expected: FAIL because `app.retrieval.retriever` does not exist.

- [ ] **Step 3: Implement retriever**

```python
from collections.abc import Callable
from contextlib import AbstractContextManager

from sqlalchemy.orm import Session

from app.retrieval.embeddings import OpenAIQueryEmbedder, QueryEmbedder
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.queries import full_text_search, read_surrounding_chunks, semantic_search
from app.retrieval.schemas import RetrievalFilters, SourcePassage


class DocumentRetriever:
    def __init__(
        self,
        *,
        session_factory: Callable[[], AbstractContextManager[Session]],
        embedder: QueryEmbedder | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._embedder = embedder or OpenAIQueryEmbedder()

    async def retrieve(
        self,
        query: str,
        *,
        top_k: int = 10,
        candidate_k: int = 50,
        filters: RetrievalFilters | None = None,
        neighbor_window: int = 1,
    ) -> list[SourcePassage]:
        if top_k < 1:
            raise ValueError("top_k must be greater than zero")
        if candidate_k < top_k:
            raise ValueError("candidate_k must be greater than or equal to top_k")

        active_filters = filters or RetrievalFilters()
        query_embedding = await self._embedder.embed_query(query)

        with self._session_factory() as session:
            semantic = semantic_search(
                session,
                query_embedding,
                limit=candidate_k,
                filters=active_filters,
            )
            full_text = full_text_search(
                session,
                query,
                limit=candidate_k,
                filters=active_filters,
            )
            fused = reciprocal_rank_fusion([semantic, full_text])[:top_k]

            passages: list[SourcePassage] = []
            for item in fused:
                previous, next_chunks = read_surrounding_chunks(
                    session,
                    item.chunk,
                    window=neighbor_window,
                )
                passages.append(
                    SourcePassage(
                        center=item,
                        previous_chunks=previous,
                        next_chunks=next_chunks,
                    )
                )
            return passages
```

Export `DocumentRetriever` from `backend/app/retrieval/__init__.py`.

- [ ] **Step 4: Run retriever tests**

Run: `cd backend && uv run pytest tests/retrieval/test_retriever.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/retrieval/__init__.py backend/app/retrieval/retriever.py backend/tests/retrieval/test_retriever.py
git commit -m "feat: add document retriever orchestration"
```

## Task 6: Optional Live Retrieval Verification

**Files:**
- Create: `backend/tests/retrieval/test_integration.py`

**Interfaces:**
- Consumes: `DocumentRetriever`
- Produces: `@pytest.mark.integration` smoke coverage for a real ingested corpus.

- [ ] **Step 1: Write skipped-by-default integration test**

```python
import asyncio
import os

import pytest

from ingest.repository import create_sessionmaker
from app.retrieval.retriever import DocumentRetriever
from app.retrieval.schemas import RetrievalFilters


pytestmark = pytest.mark.integration


def test_real_query_returns_apple_revenue_passages():
    if os.environ.get("RUN_RETRIEVAL_INTEGRATION") != "1":
        pytest.skip("set RUN_RETRIEVAL_INTEGRATION=1 to hit live Supabase/OpenAI")

    retriever = DocumentRetriever(session_factory=create_sessionmaker())

    passages = asyncio.run(
        retriever.retrieve(
            "Across Apple's latest 10-K, what happened to Services revenue?",
            top_k=5,
            candidate_k=25,
            filters=RetrievalFilters(tickers=("AAPL",), filing_types=("10-K",)),
        )
    )

    assert passages
    combined = "\n".join(passage.center.chunk.text for passage in passages)
    assert "Services" in combined or "services" in combined
    assert any(passage.center.chunk.ticker == "AAPL" for passage in passages)
```

- [ ] **Step 2: Run non-integration suite**

Run: `cd backend && uv run pytest -m "not integration" -q`

Expected: PASS. The integration test is excluded.

- [ ] **Step 3: Run live integration only after corpus ingestion is confirmed**

Run: `cd backend && RUN_RETRIEVAL_INTEGRATION=1 uv run pytest tests/retrieval/test_integration.py -q`

Expected: PASS with at least one AAPL passage containing Services/service revenue language.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/retrieval/test_integration.py
git commit -m "test: add optional retrieval integration smoke test"
```

## Task 7: Manual Verification Script And Todos Update

**Files:**
- Create: `backend/app/retrieval/debug.py`
- Modify: `docs/todos.md`

**Interfaces:**
- Consumes: `DocumentRetriever`
- Produces:
  - CLI smoke command for selected client-brief questions.
  - Checked Phase 5 items in `docs/todos.md` after tests pass.

- [ ] **Step 1: Add a tiny debug CLI**

```python
import argparse
import asyncio
from collections.abc import Sequence

from ingest.repository import create_sessionmaker
from app.retrieval.retriever import DocumentRetriever
from app.retrieval.schemas import RetrievalFilters


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a retrieval smoke query.")
    parser.add_argument("query")
    parser.add_argument("--ticker", action="append", default=[])
    parser.add_argument("--filing-type", action="append", default=[])
    parser.add_argument("--year", action="append", type=int, default=[])
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--candidate-k", type=int, default=25)
    return parser.parse_args(argv)


async def run(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    retriever = DocumentRetriever(session_factory=create_sessionmaker())
    passages = await retriever.retrieve(
        args.query,
        top_k=args.top_k,
        candidate_k=args.candidate_k,
        filters=RetrievalFilters(
            tickers=tuple(args.ticker),
            filing_types=tuple(args.filing_type),
            fiscal_years=tuple(args.year),
        ),
    )
    for index, passage in enumerate(passages, start=1):
        chunk = passage.center.chunk
        print(
            f"{index}. rrf={passage.center.rrf_score:.4f} "
            f"{chunk.citation_label} {chunk.location_label} chunk={chunk.chunk_id}"
        )
        print(chunk.text[:600].replace("\n", " "))
        print()
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    return asyncio.run(run(argv))


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run debug query after live credentials are available**

Run:

```bash
cd backend
uv run python -m app.retrieval.debug "Across Apple's 2021-2025 10-Ks, how did the revenue mix between iPhone, Services, Mac, iPad, and Wearables change?" --ticker AAPL --filing-type 10-K --top-k 5 --candidate-k 50
```

Expected: returned passages cite AAPL 10-K chunks with product-category revenue language.

- [ ] **Step 3: Mark Phase 5 complete in todos after verification**

Edit `docs/todos.md` Phase 5 only:

```markdown
- [x] `retrieval/queries.py` — pgvector semantic search over `document_chunks`
- [x] `retrieval/queries.py` — Postgres full-text search over `search_vector`
- [x] `retrieval/fusion.py` — Reciprocal Rank Fusion in Python
- [x] `retrieval/retriever.py` — query -> fused ranked passages + neighbor chunks
- [x] Unit tests: fusion ranking, query assembly (mock DB)
- [x] Integration test (optional, `@pytest.mark.integration`): real query against ingested corpus
- [x] Verify: test queries from client-brief return relevant chunks (manual or scripted)
```

If the live integration test was not run, leave the integration and verify lines unchecked and add the exact command that still needs to be run in the final handoff.

- [ ] **Step 4: Run full non-integration backend tests**

Run: `cd backend && uv run pytest -m "not integration" -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/retrieval/debug.py docs/todos.md
git commit -m "chore: verify phase 5 retrieval"
```

## Phase 6 Handoff Notes

- `DocumentRetriever.retrieve(...)` is the implementation behind the future PydanticAI `search_filings` tool.
- `read_chunk(...)` is the implementation behind the future `read_chunk` tool.
- `read_surrounding_chunks(...)` is the implementation behind the future `read_surrounding_chunks` tool.
- `SourcePassage` is intentionally Pydantic-serializable so the Phase 6 agent can return and validate grounded citations without parsing prose.
- Phase 6 should add PydanticAI usage limits around the agent loop, not inside this retrieval layer.

## Self-Review

- Spec coverage: Covers semantic search, full-text search, RRF, retriever orchestration, neighbor chunks, unit tests, optional integration test, and manual/client-brief verification.
- Cookbook alignment: Preserves separate dense/sparse retrievers and rank fusion, while replacing BM25 and numpy with pgvector and Postgres full-text search.
- PydanticAI alignment: Leaves agent implementation to Phase 6 but shapes outputs and tool boundaries for typed deps/tools/output.
- Dependency policy: Adds no runtime dependency.
- Placeholder scan: No placeholder text remains.
- Type consistency: `ChunkReference`, `RankedChunk`, `FusedChunk`, `SourcePassage`, `RetrievalFilters`, and `DocumentRetriever.retrieve(...)` signatures are consistent across tasks.
