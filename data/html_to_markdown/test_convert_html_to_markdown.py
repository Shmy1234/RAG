from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from convert_html_to_markdown import markdown_path_for, normalize_markdown, rewrite_manifest


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
    assert manifest["filings"][0]["local_path"] == (
        "2025/aapl_10-k_2025-10-31_accession.md"
    )
    assert (output_root / "manifest.json").read_text(encoding="utf-8").endswith("\n")


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
