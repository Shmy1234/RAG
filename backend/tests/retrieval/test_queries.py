from datetime import date
from types import SimpleNamespace
from uuid import UUID

from sqlalchemy.dialects import postgresql

from app.retrieval.queries import (
    build_full_text_statement,
    build_semantic_statement,
    chunk_reference_from_row,
    ranked_chunk_from_row,
)
from app.retrieval.schemas import RetrievalFilters


def row(score=0.42):
    return SimpleNamespace(
        chunk_id=UUID("00000000-0000-0000-0000-000000000001"),
        document_id=UUID("00000000-0000-0000-0000-000000000002"),
        chunk_index=3,
        text="Revenue from Services increased.",
        page_number=12,
        section="Results of Operations",
        kind="table",
        table_id=UUID("00000000-0000-0000-0000-000000000003"),
        table_title="Net Sales",
        table_units="USD millions",
        row_start=2,
        row_end=2,
        source_locator={"html_id": "sales"},
        ticker="AAPL",
        company_name="Apple Inc.",
        filing_type="10-K",
        filing_date=date(2025, 10, 31),
        fiscal_year=2025,
        accession_number="0000320193-25-000079",
        source_url="https://www.sec.gov/example",
        score=score,
    )


def compiled(statement) -> str:
    return str(statement.compile(dialect=postgresql.dialect()))


def test_chunk_reference_from_row_maps_database_fields():
    result = chunk_reference_from_row(row())

    assert result.ticker == "AAPL"
    assert result.chunk_index == 3
    assert result.location_label == "page 12, Results of Operations"
    assert result.kind == "table"
    assert result.table_title == "Net Sales"


def test_ranked_chunk_from_row_maps_database_fields():
    result = ranked_chunk_from_row(row(), rank=2, source="semantic")

    assert result.rank == 2
    assert result.score == 0.42
    assert result.source == "semantic"
    assert result.chunk.ticker == "AAPL"
    assert result.chunk.chunk_index == 3


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
    assert "document_tables" in sql


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
