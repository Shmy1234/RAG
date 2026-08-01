from datetime import date
from pathlib import Path
from uuid import uuid4

from app.database.models.documents import SourceDocument
from ingest.chunking import ChunkRecord
from ingest.manifest import IngestDocument
from ingest.repository import (
    document_chunk_values,
    source_document_kwargs,
    source_document_values,
)


def test_source_document_values_match_schema_columns():
    document = IngestDocument(
        markdown_path=Path("data/Markdown/2025/aapl.md"),
        accession_number="0000320193-25-000079",
        ticker="AAPL",
        company_name="Apple Inc.",
        filing_type="10-K",
        filing_date=date(2025, 10, 31),
        fiscal_year=2025,
        source_url="https://www.sec.gov/example",
        metadata={"local_path": "2025/aapl.md"},
    )

    values = source_document_values(document, content="# filing")

    assert values["accession_number"] == "0000320193-25-000079"
    assert values["company_name"] == "Apple Inc."
    assert values["content"] == "# filing"
    assert values["metadata"]["local_path"] == "2025/aapl.md"


def test_source_document_kwargs_uses_sqlalchemy_attribute_name():
    document = IngestDocument(
        markdown_path=Path("data/Markdown/2025/aapl.md"),
        accession_number="0000320193-25-000079",
        ticker="AAPL",
        company_name="Apple Inc.",
        filing_type="10-K",
        filing_date=date(2025, 10, 31),
        fiscal_year=2025,
        source_url="https://www.sec.gov/example",
        metadata={},
    )

    source_document = SourceDocument(**source_document_kwargs(document, "# filing"))

    assert source_document.document_metadata == {}


def test_document_chunk_values_bounds_section_for_schema():
    long_section = "A" * 300
    chunk = ChunkRecord(
        chunk_index=0,
        text="text",
        token_count=1,
        page_number=None,
        section=long_section,
        metadata={"headings": [long_section]},
    )

    values = document_chunk_values(uuid4(), chunk, [0.1])

    assert len(values["section"]) == 255
    assert values["chunk_metadata"]["headings"] == [long_section]
