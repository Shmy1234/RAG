from datetime import date

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
