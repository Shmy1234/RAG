from datetime import date
from hashlib import sha256

import pytest

from ingest.manifest import load_manifest


def test_load_manifest_maps_markdown_files_and_required_metadata(tmp_path):
    root = tmp_path / "Markdown"
    structured_root = tmp_path / "Structured"
    (root / "2025").mkdir(parents=True)
    (structured_root / "2025").mkdir(parents=True)
    (root / "2025" / "aapl.md").write_text("# Apple filing\n", encoding="utf-8")
    structured = structured_root / "2025" / "aapl.json"
    structured.write_text('{"blocks": [], "tables": []}', encoding="utf-8")
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
              "structured_local_path": "2025/aapl.json",
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
    assert doc.structured_path == structured
    assert doc.company_name == "Apple Inc."
    assert doc.filing_type == "10-K"
    assert doc.filing_date == date(2025, 10, 31)
    assert doc.fiscal_year == 2025
    assert doc.metadata["source_local_path"] == "2025/aapl.htm"


def test_load_manifest_rejects_missing_markdown_file(tmp_path):
    root = tmp_path / "Markdown"
    root.mkdir()
    (root / "manifest.json").write_text(
        '{"filings": [{"ticker": "AAPL", "form": "10-K", '
        '"filing_date": "2025-10-31", "report_date": "2025-09-27", '
        '"accession_number": "0000320193-25-000079", '
        '"source_url": "https://www.sec.gov/example", "local_path": "2025/aapl.md"}]}',
        encoding="utf-8",
    )

    try:
        load_manifest(root)
    except FileNotFoundError as exc:
        assert "2025/aapl.md" in str(exc)
    else:
        raise AssertionError("expected FileNotFoundError")


def test_load_manifest_rejects_markdown_hash_mismatch(tmp_path):
    root = tmp_path / "Markdown"
    root.mkdir()
    markdown = root / "aapl.md"
    markdown.write_text("# changed filing\n", encoding="utf-8")
    expected_hash = sha256(b"# original filing\n").hexdigest()
    (root / "manifest.json").write_text(
        '{"filings": [{"ticker": "AAPL", "form": "10-K", '
        '"filing_date": "2025-10-31", "report_date": "2025-09-27", '
        '"accession_number": "0000320193-25-000079", '
        '"source_url": "https://www.sec.gov/example", "local_path": "aapl.md", '
        f'"markdown_sha256": "{expected_hash}"}}]}}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="hash does not match"):
        load_manifest(root)


def test_load_manifest_rejects_missing_structured_artifact(tmp_path):
    root = tmp_path / "Markdown"
    root.mkdir()
    (root / "aapl.md").write_text("# filing\n", encoding="utf-8")
    (root / "manifest.json").write_text(
        '{"filings": [{"ticker": "AAPL", "form": "10-K", '
        '"filing_date": "2025-10-31", "report_date": "2025-09-27", '
        '"accession_number": "0000320193-25-000079", '
        '"source_url": "https://www.sec.gov/example", "local_path": "aapl.md"}]}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="structured_local_path"):
        load_manifest(root)
