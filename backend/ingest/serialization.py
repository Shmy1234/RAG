"""Derived representations for canonical SEC extraction artifacts."""

from dataclasses import asdict

from ingest.models import (
    EXTRACTION_VERSION,
    DocumentBlock,
    ExtractedDocument,
    ExtractedTable,
    ExtractedTableRow,
    SourceLocator,
)


def extracted_document_dict(document: ExtractedDocument) -> dict[str, object]:
    return asdict(document)


def _locator(payload: dict[str, object] | None) -> SourceLocator:
    return SourceLocator(**(payload or {}))


def load_extracted_document(payload: dict[str, object]) -> ExtractedDocument:
    extraction_version = payload.get("extraction_version")
    if extraction_version != EXTRACTION_VERSION:
        raise ValueError(
            f"unsupported extraction version {extraction_version!r}; regenerate structured artifacts"
        )
    tables = []
    for item in payload.get("tables", []):
        table = dict(item)
        rows = tuple(
            ExtractedTableRow(
                label=row["label"],
                values=tuple(row["values"]),
                is_total=row.get("is_total", False),
                source_locator=_locator(row.get("source_locator")),
            )
            for row in table["rows"]
        )
        tables.append(
            ExtractedTable(
                table_index=table["table_index"],
                title=table.get("title"),
                units=table.get("units"),
                section_path=tuple(table.get("section_path", [])),
                headers=tuple(table["headers"]),
                rows=rows,
                source_locator=_locator(table.get("source_locator")),
                footnotes=tuple(table.get("footnotes", [])),
                validation=dict(table.get("validation", {})),
            )
        )
    blocks = tuple(
        DocumentBlock(
            block_index=block["block_index"],
            kind=block["kind"],
            section_path=tuple(block.get("section_path", [])),
            text=block.get("text"),
            table_index=block.get("table_index"),
            source_locator=_locator(block.get("source_locator")),
        )
        for block in payload.get("blocks", [])
    )
    return ExtractedDocument(
        blocks=blocks,
        tables=tuple(tables),
        extraction_version=EXTRACTION_VERSION,
    )


def _table_markdown(table: ExtractedTable) -> str:
    lines = []
    if table.title:
        lines.append(f"### {table.title}")
    if table.units:
        lines.append(f"Units: {table.units}")
    lines.extend(
        [
            "| " + " | ".join(table.headers) + " |",
            "| " + " | ".join("---" for _ in table.headers) + " |",
        ]
    )
    lines.extend("| " + " | ".join((row.label, *row.values)) + " |" for row in table.rows)
    return "\n".join(lines)


def export_to_markdown(document: ExtractedDocument) -> str:
    tables = {table.table_index: table for table in document.tables}
    parts: list[str] = []
    for block in document.blocks:
        if block.kind == "text" and block.text:
            prefix = "## " if block.text.lower().startswith("item ") else ""
            parts.append(f"{prefix}{block.text}")
        elif block.kind == "table" and block.table_index is not None:
            parts.append(_table_markdown(tables[block.table_index]))
    return "\n\n".join(parts).rstrip() + "\n"
