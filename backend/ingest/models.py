"""Canonical structured-document types used by SEC ingestion."""

from dataclasses import dataclass, field
from typing import Literal

EXTRACTION_VERSION = "sec-html-v2"


@dataclass(frozen=True)
class SourceLocator:
    html_id: str | None = None
    dom_path: str | None = None
    page_label: str | None = None


@dataclass(frozen=True)
class ExtractedTableRow:
    label: str
    values: tuple[str, ...]
    is_total: bool = False
    source_locator: SourceLocator = field(default_factory=SourceLocator)


@dataclass(frozen=True)
class ExtractedTable:
    table_index: int
    title: str | None
    units: str | None
    section_path: tuple[str, ...]
    headers: tuple[str, ...]
    rows: tuple[ExtractedTableRow, ...]
    source_locator: SourceLocator
    footnotes: tuple[str, ...] = ()
    validation: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class DocumentBlock:
    block_index: int
    kind: Literal["text", "table"]
    section_path: tuple[str, ...]
    text: str | None = None
    table_index: int | None = None
    source_locator: SourceLocator = field(default_factory=SourceLocator)


@dataclass(frozen=True)
class ExtractedDocument:
    blocks: tuple[DocumentBlock, ...]
    tables: tuple[ExtractedTable, ...]
    extraction_version: str = EXTRACTION_VERSION
