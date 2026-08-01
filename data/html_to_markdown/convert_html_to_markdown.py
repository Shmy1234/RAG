from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_DIR = DATA_DIR / "downloads"
DEFAULT_OUTPUT_DIR = DATA_DIR / "Markdown"
HTML_SUFFIXES = {".htm", ".html"}
SEC_ITEM_HEADING = re.compile(r"^(Item\s+\d+[A-Z]?\.\s+.+)$", re.IGNORECASE | re.MULTILINE)


@dataclass(frozen=True)
class ConversionSummary:
    converted: int
    failed: int
    skipped: int


def markdown_path_for(source_path: Path, input_root: Path, output_root: Path) -> Path:
    relative_path = source_path.relative_to(input_root)
    return output_root / relative_path.with_suffix(".md")


def find_html_files(input_root: Path) -> list[Path]:
    return sorted(
        path
        for path in input_root.rglob("*")
        if path.is_file() and path.suffix.lower() in HTML_SUFFIXES
    )


def normalize_markdown(markdown: str) -> str:
    """Add stable structure where SEC item titles were exported as plain text."""
    return SEC_ITEM_HEADING.sub(r"## \1", markdown).rstrip() + "\n"


def rewrite_manifest(input_root: Path, output_root: Path) -> dict[str, Any] | None:
    source_manifest_path = input_root / "manifest.json"
    if not source_manifest_path.exists():
        return None

    manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    for filing in manifest.get("filings", []):
        local_path = filing.get("local_path")
        if not local_path:
            continue

        relative_path = Path(local_path)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise ValueError(
                f"Manifest local_path must be a relative path inside the download root: {local_path}"
            )

        source_path = input_root / relative_path
        markdown_path = markdown_path_for(source_path, input_root, output_root)
        if not markdown_path.is_file():
            raise FileNotFoundError(f"Manifest references missing Markdown output: {markdown_path}")
        filing["source_local_path"] = Path(local_path).as_posix()
        filing["local_path"] = markdown_path.relative_to(output_root).as_posix()

    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def convert_html_files(input_root: Path, output_root: Path, overwrite: bool) -> ConversionSummary:
    from docling.document_converter import DocumentConverter

    converter = DocumentConverter()
    converted = 0
    failed = 0
    skipped = 0

    for source_path in find_html_files(input_root):
        output_path = markdown_path_for(source_path, input_root, output_root)
        if output_path.exists() and not overwrite:
            skipped += 1
            continue

        try:
            result = converter.convert(source_path)
            markdown = normalize_markdown(result.document.export_to_markdown())
        except Exception as exc:  # noqa: BLE001 - keep processing after Docling rejects one file.
            failed += 1
            print(f"FAILED {source_path}: {exc}")
            continue

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")
        converted += 1
        print(f"WROTE {output_path}")

    rewrite_manifest(input_root, output_root)
    return ConversionSummary(converted=converted, failed=failed, skipped=skipped)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert data/downloads HTML filings to Markdown with Docling."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help=f"HTML source tree. Default: {DEFAULT_INPUT_DIR}",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Markdown output tree. Default: {DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Regenerate Markdown files that already exist.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = convert_html_files(
        input_root=args.input_dir.resolve(),
        output_root=args.output_dir.resolve(),
        overwrite=args.overwrite,
    )
    print(
        "Conversion complete: "
        f"{summary.converted} converted, {summary.skipped} skipped, {summary.failed} failed."
    )
    if summary.failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
