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
        kind="table",
        table_title="Net Sales",
        table_units="USD millions",
    )

    assert chunk.citation_label == "AAPL 10-K 2025"
    assert chunk.location_label == "page 42, Management's Discussion and Analysis"
    assert chunk.table_title == "Net Sales"
