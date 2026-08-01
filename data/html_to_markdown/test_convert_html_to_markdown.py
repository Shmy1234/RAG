from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from convert_html_to_markdown import (
    convert_html_files,
    markdown_path_for,
    normalize_markdown,
    rewrite_manifest,
)


def test_markdown_path_for_preserves_relative_tree_and_uses_md_suffix(tmp_path):
    input_root = tmp_path / "downloads"
    output_root = tmp_path / "Markdown"
    source_path = input_root / "2025" / "aapl_10-k_2025-10-31_accession.htm"

    output_path = markdown_path_for(source_path, input_root, output_root)

    assert output_path == output_root / "2025" / "aapl_10-k_2025-10-31_accession.md"


def test_rewrite_manifest_preserves_metadata_and_repoints_local_paths(tmp_path):
    input_root = tmp_path / "downloads"
    output_root = tmp_path / "Markdown"
    input_root.mkdir()
    source_path = input_root / "2025" / "aapl_10-k_2025-10-31_accession.htm"
    source_path.parent.mkdir()
    source_path.write_text("<html></html>", encoding="utf-8")
    markdown_path = output_root / "2025" / "aapl_10-k_2025-10-31_accession.md"
    markdown_path.parent.mkdir(parents=True)
    markdown_path.write_text("# Apple filing\n", encoding="utf-8")
    structured_path = (
        output_root.parent / "Structured" / "2025" / "aapl_10-k_2025-10-31_accession.json"
    )
    structured_path.parent.mkdir(parents=True)
    structured_path.write_text('{"blocks": [], "tables": []}\n', encoding="utf-8")
    (input_root / "manifest.json").write_text(
        json.dumps(
            {
                "source": "SEC EDGAR",
                "downloaded_count": 1,
                "filings": [
                    {
                        "ticker": "AAPL",
                        "local_path": "2025/aapl_10-k_2025-10-31_accession.htm",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    manifest = rewrite_manifest(input_root, output_root)

    assert manifest["source"] == "SEC EDGAR"
    assert manifest["downloaded_count"] == 1
    assert manifest["filings"][0]["ticker"] == "AAPL"
    assert manifest["filings"][0]["source_local_path"] == (
        "2025/aapl_10-k_2025-10-31_accession.htm"
    )
    assert manifest["filings"][0]["local_path"] == ("2025/aapl_10-k_2025-10-31_accession.md")
    assert len(manifest["filings"][0]["source_sha256"]) == 64
    assert len(manifest["filings"][0]["markdown_sha256"]) == 64
    assert manifest["filings"][0]["structured_local_path"].endswith(".json")
    assert len(manifest["filings"][0]["structured_sha256"]) == 64
    assert (output_root / "manifest.json").read_text(encoding="utf-8").endswith("\n")


def test_rewrite_manifest_rejects_stale_output_after_current_conversion_failure(
    tmp_path,
):
    input_root = tmp_path / "downloads"
    output_root = tmp_path / "Markdown"
    input_root.mkdir()
    source_path = input_root / "2025" / "aapl.htm"
    source_path.parent.mkdir()
    source_path.write_text("<html>new filing</html>", encoding="utf-8")
    markdown_path = output_root / "2025" / "aapl.md"
    markdown_path.parent.mkdir(parents=True)
    markdown_path.write_text("# stale filing\n", encoding="utf-8")
    (input_root / "manifest.json").write_text(
        json.dumps({"filings": [{"ticker": "AAPL", "local_path": "2025/aapl.htm"}]}),
        encoding="utf-8",
    )

    with pytest.raises(FileNotFoundError, match="current conversion run"):
        rewrite_manifest(input_root, output_root, verified_outputs=set())

    assert not (output_root / "manifest.json").exists()


def test_rewrite_manifest_refuses_to_publish_missing_markdown_output(tmp_path):
    input_root = tmp_path / "downloads"
    output_root = tmp_path / "Markdown"
    input_root.mkdir()
    (input_root / "manifest.json").write_text(
        json.dumps(
            {
                "filings": [
                    {
                        "ticker": "AAPL",
                        "local_path": "2025/missing.htm",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(FileNotFoundError, match="missing Markdown output"):
        rewrite_manifest(input_root, output_root)

    assert not (output_root / "manifest.json").exists()


def test_rewrite_manifest_refuses_to_publish_missing_structured_output(tmp_path):
    input_root = tmp_path / "downloads"
    output_root = tmp_path / "Markdown"
    input_root.mkdir()
    source = input_root / "filing.htm"
    source.write_text("<html></html>")
    output_root.mkdir()
    (output_root / "filing.md").write_text("filing")
    (input_root / "manifest.json").write_text(
        json.dumps({"filings": [{"ticker": "AAPL", "local_path": "filing.htm"}]}),
        encoding="utf-8",
    )

    with pytest.raises(FileNotFoundError, match="structured output"):
        rewrite_manifest(input_root, output_root)

    assert not (output_root / "manifest.json").exists()


def test_rewrite_manifest_rejects_paths_outside_download_root(tmp_path):
    input_root = tmp_path / "downloads"
    output_root = tmp_path / "Markdown"
    input_root.mkdir()
    (input_root / "manifest.json").write_text(
        json.dumps({"filings": [{"ticker": "AAPL", "local_path": "../outside.htm"}]}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="relative path inside the download root"):
        rewrite_manifest(input_root, output_root)

    assert not (output_root / "manifest.json").exists()


def test_normalize_markdown_marks_sec_items_as_headings():
    markdown = "Item 1. Business\n\nBusiness details.\n\nITEM 1A. RISK FACTORS\n"

    normalized = normalize_markdown(markdown)

    assert "## Item 1. Business" in normalized
    assert "## ITEM 1A. RISK FACTORS" in normalized


def test_convert_html_files_uses_sec_aware_table_extraction(tmp_path):
    input_root = tmp_path / "downloads"
    output_root = tmp_path / "Markdown"
    source_path = input_root / "2025" / "aapl.htm"
    source_path.parent.mkdir(parents=True)
    source_path.write_text(
        """
        <html><body><div>Item 7. Results</div><div>Segment Results</div>
        <p>The following table is in millions:</p>
        <table><tr><td></td><td>2025</td><td>2024</td></tr>
        <tr><td>Americas</td><td>$</td><td>10</td><td>$</td><td>9</td></tr></table>
        </body></html>
        """,
        encoding="utf-8",
    )

    summary = convert_html_files(input_root, output_root, overwrite=True)

    assert summary.converted == 1
    markdown = (output_root / "2025" / "aapl.md").read_text(encoding="utf-8")
    assert "| Segment | 2025 | 2024 |" in markdown
    assert "| Americas | $10 | $9 |" in markdown
    structured = output_root.parent / "Structured" / "2025" / "aapl.json"
    payload = json.loads(structured.read_text(encoding="utf-8"))
    assert payload["tables"][0]["rows"][0]["label"] == "Americas"


def test_convert_regenerates_legacy_markdown_when_structured_artifact_is_missing(
    tmp_path,
):
    input_root = tmp_path / "downloads"
    output_root = tmp_path / "Markdown"
    input_root.mkdir()
    output_root.mkdir()
    (input_root / "filing.htm").write_text("<html><body><p>Visible filing.</p></body></html>")
    (output_root / "filing.md").write_text("legacy output")

    summary = convert_html_files(input_root, output_root, overwrite=False)

    assert summary.converted == 1
    assert summary.skipped == 0
    assert (output_root.parent / "Structured" / "filing.json").is_file()


def test_convert_regenerates_stale_structured_extraction_version(tmp_path):
    input_root = tmp_path / "downloads"
    output_root = tmp_path / "Markdown"
    structured_root = tmp_path / "Structured"
    input_root.mkdir()
    output_root.mkdir()
    structured_root.mkdir()
    (input_root / "filing.htm").write_text("<html><body><p>Current filing.</p></body></html>")
    (output_root / "filing.md").write_text("stale output")
    (structured_root / "filing.json").write_text(
        json.dumps({"blocks": [], "tables": [], "extraction_version": "sec-html-v1"})
    )

    summary = convert_html_files(input_root, output_root, overwrite=False)

    assert summary.converted == 1
    payload = json.loads((structured_root / "filing.json").read_text())
    assert payload["extraction_version"] == "sec-html-v2"
