"""Manifest loading and source-document metadata for local filings."""

import json
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from pathlib import Path
from typing import Any

COMPANY_NAMES = {
    "AAPL": "Apple Inc.",
    "MSFT": "Microsoft Corporation",
    "NVDA": "NVIDIA Corporation",
    "AMZN": "Amazon.com, Inc.",
    "GOOGL": "Alphabet Inc.",
}


@dataclass(frozen=True)
class IngestDocument:
    markdown_path: Path
    accession_number: str
    ticker: str
    company_name: str
    filing_type: str
    filing_date: date
    fiscal_year: int
    source_url: str
    metadata: dict[str, Any]


def load_manifest(markdown_root: Path) -> list[IngestDocument]:
    """Load the Markdown manifest and verify every referenced file exists."""
    manifest_path = markdown_root / "manifest.json"
    with manifest_path.open(encoding="utf-8") as file:
        payload = json.load(file)

    documents: list[IngestDocument] = []
    for filing in payload["filings"]:
        relative_path = Path(filing["local_path"])
        markdown_path = markdown_root / relative_path
        if not markdown_path.is_file():
            raise FileNotFoundError(f"Markdown file listed in manifest does not exist: {relative_path}")
        expected_hash = filing.get("markdown_sha256")
        if expected_hash is not None:
            actual_hash = sha256(markdown_path.read_bytes()).hexdigest()
            if actual_hash != expected_hash:
                raise ValueError(f"Markdown hash does not match manifest: {relative_path}")

        report_date = date.fromisoformat(filing["report_date"])
        documents.append(
            IngestDocument(
                markdown_path=markdown_path,
                accession_number=filing["accession_number"],
                ticker=filing["ticker"],
                company_name=COMPANY_NAMES.get(filing["ticker"], filing["ticker"]),
                filing_type=filing["form"],
                filing_date=date.fromisoformat(filing["filing_date"]),
                fiscal_year=report_date.year,
                source_url=filing["source_url"],
                metadata=dict(filing),
            )
        )

    return documents
