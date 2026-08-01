from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as temporary:
            temporary.write(content)
            temporary_path = Path(temporary.name)
        temporary_path.replace(path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def rewrite_manifest(
    input_root: Path,
    output_root: Path,
    *,
    verified_outputs: set[Path] | None = None,
) -> dict[str, Any] | None:
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
        if verified_outputs is not None and markdown_path not in verified_outputs:
            raise FileNotFoundError(
                f"Manifest output was not verified in the current conversion run: {markdown_path}"
            )
        if not markdown_path.is_file():
            raise FileNotFoundError(f"Manifest references missing Markdown output: {markdown_path}")
        filing["source_local_path"] = Path(local_path).as_posix()
        filing["local_path"] = markdown_path.relative_to(output_root).as_posix()
        filing["source_sha256"] = sha256_file(source_path)
        filing["markdown_sha256"] = sha256_file(markdown_path)
        structured_root = output_root.parent / "Structured"
        structured_path = structured_root / relative_path.with_suffix(".json")
        if not structured_path.is_file():
            raise FileNotFoundError(
                f"Manifest references missing structured output: {structured_path}"
            )
        filing["structured_local_path"] = structured_path.relative_to(structured_root).as_posix()
        filing["structured_sha256"] = sha256_file(structured_path)
        filing["extraction_version"] = "sec-html-v1"

    write_text_atomic(output_root / "manifest.json", json.dumps(manifest, indent=2) + "\n")
    return manifest


def convert_html_files(input_root: Path, output_root: Path, overwrite: bool) -> ConversionSummary:
    from ingest.sec_html import extract_sec_html
    from ingest.serialization import export_to_markdown, extracted_document_dict

    structured_root = output_root.parent / "Structured"
    converted = 0
    failed = 0
    skipped = 0
    verified_outputs: set[Path] = set()

    for source_path in find_html_files(input_root):
        output_path = markdown_path_for(source_path, input_root, output_root)
        structured_path = structured_root / source_path.relative_to(input_root).with_suffix(".json")
        if output_path.exists() and structured_path.exists() and not overwrite:
            skipped += 1
            verified_outputs.add(output_path)
            continue

        try:
            document = extract_sec_html(source_path.read_bytes())
            markdown = export_to_markdown(document)
            structured = json.dumps(extracted_document_dict(document), indent=2) + "\n"
        except Exception as exc:  # noqa: BLE001 - keep processing after one malformed filing.
            failed += 1
            print(f"FAILED {source_path}: {exc}")
            continue

        write_text_atomic(output_path, markdown)
        write_text_atomic(structured_path, structured)
        verified_outputs.add(output_path)
        converted += 1
        print(f"WROTE {output_path}")

    if failed == 0:
        rewrite_manifest(input_root, output_root, verified_outputs=verified_outputs)
    return ConversionSummary(converted=converted, failed=failed, skipped=skipped)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert SEC HTML filings to Markdown and canonical structured JSON."
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
