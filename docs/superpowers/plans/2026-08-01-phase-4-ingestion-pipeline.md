# Phase 4 Ingestion Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a one-off ingestion pipeline that reads local Docling Markdown filings, chunks them with Docling, embeds chunks with OpenAI, and writes `source_documents` plus `document_chunks` into Supabase Postgres.

**Architecture:** The pipeline lives under `backend/ingest/` and is run from the backend Python environment. It loads `data/Markdown/manifest.json`, converts each Markdown file back into a Docling document, creates retrieval chunks with Docling `HybridChunker` using an OpenAI tokenizer, preserves structural metadata from Docling chunks, embeds in bounded batches, and writes through SQLAlchemy models to Supabase Postgres. The CLI must support dry runs and an explicit one-chunk smoke test before full ingestion.

**Tech Stack:** Python 3.12, Docling `DocumentConverter`, Docling `HierarchicalChunker`, Docling `HybridChunker`, `tiktoken`, OpenAI Python SDK embeddings API, SQLAlchemy, pgvector, Supabase Postgres.

## Global Constraints

- Do not run full-corpus ingestion or full-corpus embeddings until the user explicitly approves it.
- The first paid OpenAI call must be a single-chunk smoke test using `--limit-documents 1 --limit-chunks 1 --upload`.
- Use `app.config.settings` for `DATABASE_URL`, `OPENAI_API_KEY`, `OPENAI_EMBEDDING_MODEL`, and `OPENAI_EMBEDDING_DIMENSIONS`; do not call `os.getenv`.
- Current repo defaults are `OPENAI_EMBEDDING_MODEL="text-embedding-3-small"` and `OPENAI_EMBEDDING_DIMENSIONS=1536`.
- The database column is `document_chunks.embedding vector(1536)`, so embeddings must be created with `dimensions=settings.OPENAI_EMBEDDING_DIMENSIONS`.
- OpenAI embeddings inputs must stay below the current API limit of 8192 tokens per input; embedding batches must stay below 300,000 total input tokens.
- Use Docling Markdown files from `data/Markdown/`, not the raw HTML files from `data/downloads/`.
- Ingestion must be idempotent by default: skip already-ingested accession numbers unless `--replace` is passed.
- Do not manually modify Supabase tables outside Alembic-managed schema and SQLAlchemy model writes.

---

## Source Notes

- Docling docs show Markdown can be converted to a Docling document with `DocumentConverter().convert(source).document`.
- Docling docs show `HierarchicalChunker().chunk(doc)` creates structure-aware chunks.
- Docling docs show `HybridChunker(tokenizer=OpenAITokenizer(...), merge_peers=True)` chunks a Docling document and `chunker.contextualize(chunk)` creates context-rich text for embeddings.
- OpenAI docs show embeddings support `text-embedding-3-small` and a `dimensions` parameter for `text-embedding-3` models.
- OpenAI docs/API search state current embedding inputs are capped at 8192 tokens per input and 300,000 tokens total per request.

## File Structure

- Create `backend/ingest/manifest.py`: load and validate `data/Markdown/manifest.json`, resolve Markdown paths, derive company names and fiscal years.
- Create `backend/ingest/chunking.py`: convert Markdown to `DoclingDocument`, run hierarchical diagnostics, run hybrid chunking, and produce typed chunk records.
- Create `backend/ingest/embeddings.py`: count tokens, batch chunk texts under OpenAI limits, call embeddings API, and validate vector dimensions.
- Create `backend/ingest/repository.py`: open SQLAlchemy sessions and upsert/replace `SourceDocument` plus `DocumentChunk` rows.
- Create `backend/ingest/run.py`: CLI entrypoint for dry run, one-chunk smoke test, one-document run, and full run.
- Create `backend/tests/ingest/test_manifest.py`: unit tests for manifest parsing and metadata derivation.
- Create `backend/tests/ingest/test_chunking.py`: unit tests for chunk record shaping and token bounds with a fake Docling chunk.
- Create `backend/tests/ingest/test_embeddings.py`: unit tests for embedding batching and dimension validation without network.
- Create `backend/tests/ingest/test_repository.py`: unit tests for repository write planning with mocked session boundaries.
- Modify `backend/pyproject.toml`: expose an ingest script if desired, for example `document-copilot-ingest = "ingest.run:main"`.
- Modify `docs/todos.md`: mark Phase 4 subtasks only after implementation and verification.

## Task 1: Manifest Loading And Document Metadata

**Files:**
- Create: `backend/ingest/manifest.py`
- Test: `backend/tests/ingest/test_manifest.py`

**Interfaces:**
- Produces:
  - `COMPANY_NAMES: dict[str, str]`
  - `IngestDocument` dataclass with `markdown_path: Path`, `accession_number: str`, `ticker: str`, `company_name: str`, `filing_type: str`, `filing_date: date`, `fiscal_year: int`, `source_url: str`, `metadata: dict[str, Any]`
  - `load_manifest(markdown_root: Path) -> list[IngestDocument]`

- [x] **Step 1: Write failing manifest tests**

```python
from datetime import date
from pathlib import Path

from ingest.manifest import load_manifest


def test_load_manifest_maps_markdown_files_and_required_metadata(tmp_path):
    root = tmp_path / "Markdown"
    (root / "2025").mkdir(parents=True)
    (root / "2025" / "aapl.md").write_text("# Apple filing\n", encoding="utf-8")
    (root / "manifest.json").write_text(
        """
        {
          "filings": [
            {
              "ticker": "AAPL",
              "form": "10-K",
              "filing_date": "2025-10-31",
              "report_date": "2025-09-27",
              "accession_number": "0000320193-25-000079",
              "source_url": "https://www.sec.gov/example",
              "local_path": "2025/aapl.md",
              "source_local_path": "2025/aapl.htm"
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    documents = load_manifest(root)

    assert len(documents) == 1
    doc = documents[0]
    assert doc.markdown_path == root / "2025" / "aapl.md"
    assert doc.company_name == "Apple Inc."
    assert doc.filing_type == "10-K"
    assert doc.filing_date == date(2025, 10, 31)
    assert doc.fiscal_year == 2025
    assert doc.metadata["source_local_path"] == "2025/aapl.htm"
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/ingest/test_manifest.py -q`

Expected: FAIL because `ingest.manifest` does not exist.

- [x] **Step 3: Implement manifest loading**

Implement `IngestDocument`, `COMPANY_NAMES`, JSON parsing, date parsing, fiscal year derivation from `report_date[:4]`, and a clear `FileNotFoundError` if a manifest path points to a missing Markdown file.

Use this mapping:

```python
COMPANY_NAMES = {
    "AAPL": "Apple Inc.",
    "MSFT": "Microsoft Corporation",
    "NVDA": "NVIDIA Corporation",
    "AMZN": "Amazon.com, Inc.",
    "GOOGL": "Alphabet Inc.",
}
```

- [x] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/ingest/test_manifest.py -q`

Expected: PASS.

## Task 2: Docling Chunking Layer

**Files:**
- Create: `backend/ingest/chunking.py`
- Test: `backend/tests/ingest/test_chunking.py`

**Interfaces:**
- Consumes: `IngestDocument`
- Produces:
  - `ChunkRecord` dataclass with `chunk_index: int`, `text: str`, `token_count: int`, `page_number: int | None`, `section: str | None`, `metadata: dict[str, Any]`
  - `build_openai_tokenizer(model: str, max_tokens: int) -> OpenAITokenizer`
  - `chunk_markdown_document(document: IngestDocument, embedding_model: str, max_tokens: int = 1200) -> list[ChunkRecord]`

- [x] **Step 1: Write failing chunk-shaping tests**

```python
from ingest.chunking import metadata_from_chunk, section_from_headings


class FakeOrigin:
    page_no = 7


class FakeMeta:
    headings = ["Item 8", "Consolidated Statements of Operations"]
    captions = ["In millions"]
    origin = FakeOrigin()


class FakeChunk:
    text = "Total net sales | 416,161 | 391,035"
    meta = FakeMeta()


def test_section_from_headings_uses_deepest_heading():
    assert section_from_headings(["Item 8", "Balance Sheets"]) == "Balance Sheets"


def test_metadata_from_chunk_preserves_docling_context():
    metadata = metadata_from_chunk(FakeChunk())

    assert metadata["headings"] == ["Item 8", "Consolidated Statements of Operations"]
    assert metadata["captions"] == ["In millions"]
    assert metadata["docling_page_number"] == 7
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/ingest/test_chunking.py -q`

Expected: FAIL because `ingest.chunking` does not exist.

- [x] **Step 3: Implement chunking helpers and chunking function**

Implementation requirements:

```python
import tiktoken
from docling.chunking import HierarchicalChunker, HybridChunker
from docling.document_converter import DocumentConverter
from docling_core.transforms.chunker.tokenizer.openai import OpenAITokenizer


def build_openai_tokenizer(model: str, max_tokens: int) -> OpenAITokenizer:
    return OpenAITokenizer(
        tokenizer=tiktoken.encoding_for_model(model),
        max_tokens=max_tokens,
    )
```

Use `DocumentConverter().convert(document.markdown_path).document`.

Run `HierarchicalChunker().chunk(dl_doc)` for diagnostics and store `hierarchical_chunk_count` in each chunk metadata or a document-level ingest report. Run `HybridChunker(tokenizer=tokenizer, merge_peers=True).chunk(dl_doc=dl_doc)` for final retrieval chunks.

Use `hybrid_chunker.contextualize(chunk)` as the stored/embedded `text` so headings and captions travel with the chunk. Store the raw `chunk.text` in `metadata["raw_text"]` when it differs from contextualized text.

Use `max_tokens=1200` as the default retrieval chunk target. This is intentionally below the OpenAI hard limit of 8192 tokens per input and gives better retrieval granularity for long 10-K filings. Reject any post-contextualization chunk over 8192 tokens.

- [x] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/ingest/test_chunking.py -q`

Expected: PASS.

## Task 3: Embedding Batching And OpenAI Boundary

**Files:**
- Create: `backend/ingest/embeddings.py`
- Test: `backend/tests/ingest/test_embeddings.py`

**Interfaces:**
- Consumes: `ChunkRecord`
- Produces:
  - `count_embedding_tokens(text: str, model: str) -> int`
  - `batch_embedding_inputs(chunks: list[ChunkRecord], max_batch_tokens: int = 250_000, max_batch_items: int = 256) -> list[list[ChunkRecord]]`
  - `embed_texts(texts: list[str], model: str, dimensions: int) -> list[list[float]]`

- [x] **Step 1: Write failing batching tests**

```python
from ingest.chunking import ChunkRecord
from ingest.embeddings import batch_embedding_inputs, validate_embedding_dimensions


def chunk(index: int, token_count: int) -> ChunkRecord:
    return ChunkRecord(
        chunk_index=index,
        text=f"chunk {index}",
        token_count=token_count,
        page_number=None,
        section=None,
        metadata={},
    )


def test_batch_embedding_inputs_respects_total_token_budget():
    batches = batch_embedding_inputs(
        [chunk(0, 700), chunk(1, 700), chunk(2, 700)],
        max_batch_tokens=1400,
        max_batch_items=10,
    )

    assert [[item.chunk_index for item in batch] for batch in batches] == [[0, 1], [2]]


def test_validate_embedding_dimensions_rejects_wrong_vector_size():
    try:
        validate_embedding_dimensions([[0.1, 0.2]], dimensions=1536)
    except ValueError as exc:
        assert "1536" in str(exc)
    else:
        raise AssertionError("expected ValueError")
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/ingest/test_embeddings.py -q`

Expected: FAIL because `ingest.embeddings` does not exist.

- [x] **Step 3: Implement embedding helpers**

Use OpenAI SDK:

```python
from openai import OpenAI

client = OpenAI(api_key=settings.OPENAI_API_KEY)
response = client.embeddings.create(
    model=model,
    input=texts,
    dimensions=dimensions,
    encoding_format="float",
)
vectors = [item.embedding for item in response.data]
```

Guardrails:

- Reject empty strings before calling OpenAI.
- Reject any single chunk over 8192 tokens.
- Keep each request below `250_000` tokens to leave margin under OpenAI's 300,000-token batch cap.
- Validate every returned vector length equals `settings.OPENAI_EMBEDDING_DIMENSIONS`.

- [x] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/ingest/test_embeddings.py -q`

Expected: PASS.

## Task 4: Database Repository Writes

**Files:**
- Create: `backend/ingest/repository.py`
- Test: `backend/tests/ingest/test_repository.py`

**Interfaces:**
- Consumes: `IngestDocument`, `ChunkRecord`, embeddings
- Produces:
  - `create_sessionmaker() -> sessionmaker[Session]`
  - `document_exists(session: Session, accession_number: str) -> bool`
  - `replace_document(session: Session, document: IngestDocument, content: str) -> SourceDocument`
  - `insert_chunks(session: Session, source_document: SourceDocument, chunks: list[ChunkRecord], embeddings: list[list[float]]) -> None`

- [x] **Step 1: Write failing repository tests**

```python
from datetime import date
from pathlib import Path

from ingest.manifest import IngestDocument
from ingest.repository import source_document_values


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
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/ingest/test_repository.py -q`

Expected: FAIL because `ingest.repository` does not exist.

- [x] **Step 3: Implement repository**

Use SQLAlchemy models from `app.database.models.documents`.

Default behavior:

- If `document_exists(...)` and `replace=False`, skip the accession number.
- If `replace=True`, delete the existing `SourceDocument`; cascade removes `DocumentChunk`.
- Insert one `SourceDocument` with full Markdown content.
- Insert `DocumentChunk` rows with stable `chunk_index` order, `page_number`, `section`, `text`, `token_count`, `metadata`, and matching vector embedding.

Use the direct `settings.sqlalchemy_database_url`, not the Supabase REST client, because the schema already uses SQLAlchemy and `pgvector.sqlalchemy.Vector`.

- [x] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/ingest/test_repository.py -q`

Expected: PASS.

## Task 5: CLI Orchestration And Cost Gates

**Files:**
- Create: `backend/ingest/run.py`
- Modify: `backend/pyproject.toml`
- Test: `backend/tests/ingest/test_run.py`

**Interfaces:**
- Consumes all previous tasks.
- Produces CLI flags:
  - `--markdown-root ../data/Markdown`
  - `--dry-run`
  - `--upload`
  - `--replace`
  - `--limit-documents N`
  - `--limit-chunks N`
  - `--max-chunk-tokens 1200`
  - `--embedding-batch-token-limit 250000`

- [x] **Step 1: Write failing CLI argument tests**

```python
from ingest.run import parse_args


def test_parse_args_defaults_to_dry_run_without_upload():
    args = parse_args([])

    assert args.dry_run is True
    assert args.upload is False
    assert args.max_chunk_tokens == 1200


def test_parse_args_upload_disables_dry_run_when_explicit():
    args = parse_args(["--upload", "--limit-documents", "1", "--limit-chunks", "1"])

    assert args.upload is True
    assert args.limit_documents == 1
    assert args.limit_chunks == 1
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/ingest/test_run.py -q`

Expected: FAIL because `ingest.run` does not exist.

- [x] **Step 3: Implement CLI orchestration**

Required behavior:

- Default run is dry-run only: load manifest, chunk documents, estimate tokens/chunks, and print summary.
- `--upload` is required before any OpenAI API or database writes happen.
- `--limit-documents 1 --limit-chunks 1 --upload` performs the single paid smoke test.
- Before full upload, print estimated document count, chunk count, and token count and require a `--yes` flag.
- For dry-run, do not instantiate `OpenAI` and do not open a DB session.
- For upload, process one document transactionally: source document and all selected chunks commit together.
- Log every skipped accession number.

- [x] **Step 4: Add script entrypoint**

Add to `backend/pyproject.toml`:

```toml
[project.scripts]
document-copilot-ingest = "ingest.run:main"
```

If the project already has `[project.scripts]`, append the entry without duplicating the section.

- [x] **Step 5: Run tests**

Run: `cd backend && uv run pytest tests/ingest -q`

Expected: PASS with no network or database access.

## Task 6: Manual Verification Sequence Before Full Run

**Files:**
- Modify: `docs/todos.md`
- No automated test file.

**Interfaces:**
- Consumes the CLI from Task 5.
- Produces a documented execution checklist.

- [x] **Step 1: Dry-run chunking only**

Run after implementation:

```bash
cd backend
uv run document-copilot-ingest --dry-run --limit-documents 1
```

Expected:

- No OpenAI call.
- No Supabase write.
- Prints one document, chunk count, token count, max chunk tokens, and sample sections.

- [x] **Step 2: Single-chunk paid smoke test**

Run only after user approval:

```bash
cd backend
uv run document-copilot-ingest --upload --limit-documents 1 --limit-chunks 1
```

Expected:

- Creates or skips one `source_documents` row.
- Creates exactly one `document_chunks` row.
- Embedding vector length is `1536`.
- `search_vector` is populated by Postgres generated column.

Execution result on 2026-08-01: succeeded with one uploaded AAPL source document,
one chunk, and one embedding. The command reported `uploaded ... chunks=1 embeddings=1`.

- [x] **Step 3: Database verification query**

Run after the single-chunk upload:

```sql
select
  sd.ticker,
  sd.fiscal_year,
  dc.chunk_index,
  dc.token_count,
  vector_dims(dc.embedding) as embedding_dimensions,
  left(dc.text, 120) as text_preview
from document_chunks dc
join source_documents sd on sd.id = dc.document_id
order by sd.created_at desc, dc.chunk_index asc
limit 1;
```

Expected:

- `embedding_dimensions = 1536`
- `token_count <= 1200` for normal chunks, and always `< 8192`
- `text_preview` contains readable filing context.

Execution result on 2026-08-01: AAPL 2025 chunk `0` returned `token_count=697`,
`embedding_dimensions=1536`, and `has_search_vector=true`.

- [x] **Step 4: One-document upload**

Run only after the single-chunk DB check passes:

```bash
cd backend
uv run document-copilot-ingest --upload --replace --limit-documents 1 --yes
```

Expected:

- One source document.
- Many chunks.
- No duplicate `(document_id, chunk_index)` rows.

Execution result on 2026-08-01: AAPL 2025 committed with 138 chunks, all 1536-dimensional
embeddings, populated search vectors, and no duplicate chunk indices.

- [x] **Step 5: Full-corpus upload**

Run only after user approval and one-document verification:

```bash
cd backend
uv run document-copilot-ingest --upload --yes
```

Expected:

- Up to 25 source documents from `data/Markdown/manifest.json`.
- Chunks for every non-skipped source document.
- Idempotent rerun skips the same 25 accession numbers unless `--replace` is passed.

Execution result on 2026-08-01: 25 source documents and 4,641 chunks are present in
Supabase. The final rerun reported `uploaded=0 skipped=25`.

## Self-Review

- Spec coverage: covers local Markdown loading, Docling hierarchical and hybrid chunking, OpenAI embeddings, Supabase Postgres writes, idempotency, tests, and the one-chunk paid smoke test gate.
- Placeholder scan: no task contains a placeholder step; every implementation task includes expected files, interfaces, tests, and commands.
- Type consistency: `IngestDocument` and `ChunkRecord` are introduced before downstream tasks consume them; CLI flags match verification commands.
