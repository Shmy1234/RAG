from datetime import date
from pathlib import Path
from uuid import uuid4

from app.database.models.documents import SourceDocument
from ingest.chunking import ChunkRecord
from ingest.manifest import IngestDocument
from ingest.models import ExtractedTable, ExtractedTableRow, SourceLocator
from ingest.repository import (
    document_chunk_values,
    document_table_values,
    source_document_kwargs,
    source_document_values,
)


def test_source_document_values_match_schema_columns():
    document = IngestDocument(
        markdown_path=Path("data/Markdown/2025/aapl.md"),
        structured_path=Path("data/Structured/2025/aapl.json"),
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
        structured_path=Path("data/Structured/2025/aapl.json"),
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


def test_document_table_values_preserve_logical_rows_and_provenance():
    table = ExtractedTable(
        table_index=3,
        title="Segment Results",
        units="USD millions",
        section_path=("Item 7", "Segment Results"),
        headers=("Segment", "2025"),
        rows=(ExtractedTableRow(label="Americas", values=("$10",)),),
        source_locator=SourceLocator(html_id="segments", dom_path="/html/body/table[1]"),
        validation={"status": "passed"},
    )

    values = document_table_values(uuid4(), table)

    assert values["table_index"] == 3
    assert values["columns"] == ["Segment", "2025"]
    assert values["rows"][0]["label"] == "Americas"
    assert values["source_locator"]["html_id"] == "segments"


def test_document_chunk_values_links_table_chunk():
    table_id = uuid4()
    chunk = ChunkRecord(
        chunk_index=0,
        text="Revenue | $10",
        token_count=4,
        page_number=None,
        section="Item 7",
        metadata={"source_locator": {"html_id": "results"}},
        kind="table",
        table_index=3,
        row_start=2,
        row_end=2,
    )

    values = document_chunk_values(uuid4(), chunk, [0.1], table_id=table_id)

    assert values["table_id"] == table_id
    assert values["kind"] == "table"
    assert values["row_start"] == 2
