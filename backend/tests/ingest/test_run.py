from dataclasses import replace
from datetime import date
from pathlib import Path

from ingest.chunking import ChunkRecord
from ingest.manifest import IngestDocument
from ingest.run import PreparedDocument, parse_args, validate_prepared_documents


def test_parse_args_defaults_to_dry_run_without_upload():
    args = parse_args([])

    assert args.dry_run is True
    assert args.upload is False
    assert args.max_chunk_tokens == 1200


def test_parse_args_upload_disables_dry_run_when_explicit():
    args = parse_args(["--upload", "--limit-documents", "1", "--limit-chunks", "1"])

    assert args.upload is True
    assert args.dry_run is False
    assert args.limit_documents == 1
    assert args.limit_chunks == 1


def test_parse_args_supports_embedding_budget_and_confirmation():
    args = parse_args(
        ["--upload", "--yes", "--embedding-batch-token-limit", "1000"]
    )

    assert args.yes is True
    assert args.embedding_batch_token_limit == 1000


def prepared_document(*chunks: ChunkRecord) -> PreparedDocument:
    document = IngestDocument(
        markdown_path=Path("aapl.md"),
        accession_number="0000320193-25-000079",
        ticker="AAPL",
        company_name="Apple Inc.",
        filing_type="10-K",
        filing_date=date(2025, 10, 31),
        fiscal_year=2025,
        source_url="https://www.sec.gov/example",
        metadata={},
    )
    return PreparedDocument(document=document, content="# filing", chunks=list(chunks))


def chunk(index: int, text: str) -> ChunkRecord:
    return ChunkRecord(
        chunk_index=index,
        text=text,
        token_count=5,
        page_number=None,
        section="Item 1",
        metadata={},
    )


def test_validate_prepared_documents_reports_corpus_quality():
    report = validate_prepared_documents(
        [prepared_document(chunk(0, "Revenue increased."), chunk(1, "Margins declined."))]
    )

    assert report.document_count == 1
    assert report.chunk_count == 2
    assert report.chunks_without_section == 0


def test_validate_prepared_documents_reports_duplicate_chunk_text():
    original = chunk(0, "Revenue increased.")
    duplicate = replace(original, chunk_index=1)

    report = validate_prepared_documents([prepared_document(original, duplicate)])

    assert report.duplicate_chunk_count == 1
