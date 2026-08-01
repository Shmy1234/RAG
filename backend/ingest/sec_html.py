"""Deterministic block and table extraction for SEC filing HTML."""

import re
from dataclasses import replace

from lxml import etree, html

from ingest.models import DocumentBlock, ExtractedDocument, SourceLocator
from ingest.table_normalizer import normalize_table_html

_ITEM = re.compile(r"^Item\s+\d+[A-Z]?\.\s+", re.IGNORECASE)
_ITEM_ONLY = re.compile(r"^Item\s+\d+[A-Z]?\.$", re.IGNORECASE)
_TABLE_LEAD = re.compile(r"\b(?:following|below)\s+table\b", re.IGNORECASE)
_BLOCK_TAGS = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "table"}


def _text(element) -> str:
    return " ".join(element.text_content().replace("\u00a0", " ").split())


def _table_text(element) -> str:
    cells = element.xpath(".//th|.//td")
    return " ".join(text for cell in cells if (text := _text(cell)))


def _hidden(element) -> bool:
    hidden_by_ancestor = any(
        ancestor.tag.lower() in {"ix:hidden", "script", "style"}
        for ancestor in (element, *element.iterancestors())
        if isinstance(ancestor.tag, str)
    )
    hidden_metadata_child = any(
        isinstance(descendant.tag, str) and descendant.tag.lower() in {"ix:header", "ix:hidden"}
        for descendant in element.iterdescendants()
    )
    return hidden_by_ancestor or hidden_metadata_child


def _units(text: str) -> str | None:
    lowered = text.casefold()
    if "dollars in millions" in lowered or "in millions" in lowered:
        return "USD millions"
    if "dollars in billions" in lowered or "in billions" in lowered:
        return "USD billions"
    return None


def extract_sec_html(source: str | bytes) -> ExtractedDocument:
    """Extract visible SEC blocks in DOM order and normalize semantic tables."""
    root = html.fromstring(source)
    tree = root.getroottree()
    candidates = root.xpath(
        "//p[not(ancestor::table)]"
        "|//div[not(ancestor::table) and not(.//p or .//div or .//table)]"
        "|//h1[not(ancestor::table)]|//h2[not(ancestor::table)]"
        "|//h3[not(ancestor::table)]|//h4[not(ancestor::table)]"
        "|//h5[not(ancestor::table)]|//h6[not(ancestor::table)]"
        "|//table[not(ancestor::table)]"
    )
    blocks: list[DocumentBlock] = []
    tables = []
    section: str | None = None
    pending_item_index: int | None = None
    recent_text: list[str] = []

    for element in candidates:
        if _hidden(element):
            continue
        tag = element.tag.lower()
        locator = SourceLocator(html_id=element.get("id"), dom_path=tree.getpath(element))
        if tag != "table":
            text = _text(element)
            if not text:
                continue
            if pending_item_index is not None:
                combined = f"{blocks[pending_item_index].text} {text}"
                section = combined
                blocks[pending_item_index] = replace(
                    blocks[pending_item_index],
                    text=combined,
                    section_path=(combined,),
                )
                recent_text[-1] = combined
                pending_item_index = None
                continue
            if _ITEM.match(text):
                section = text
            recent_text.append(text)
            recent_text = recent_text[-3:]
            blocks.append(
                DocumentBlock(
                    block_index=len(blocks),
                    kind="text",
                    section_path=(section,) if section else (),
                    text=text,
                    source_locator=locator,
                )
            )
            if _ITEM_ONLY.match(text):
                section = text
                pending_item_index = len(blocks) - 1
            continue

        caption = recent_text[-1] if recent_text else ""
        title = None
        if _TABLE_LEAD.search(caption) and len(recent_text) > 1:
            title = recent_text[-2]
        elif caption and len(caption) <= 120:
            title = caption
        table = normalize_table_html(
            etree.tostring(element, encoding="unicode", method="html"),
            table_index=len(tables),
            title=title,
            units=_units(caption),
            section_path=(section,) if section else (),
        )
        if table is None:
            text = _table_text(element)
            if text:
                blocks.append(
                    DocumentBlock(
                        block_index=len(blocks),
                        kind="text",
                        section_path=(section,) if section else (),
                        text=text,
                        source_locator=locator,
                    )
                )
            continue
        tables.append(table)
        blocks.append(
            DocumentBlock(
                block_index=len(blocks),
                kind="table",
                section_path=table.section_path,
                table_index=table.table_index,
                source_locator=locator,
            )
        )

    return ExtractedDocument(blocks=tuple(blocks), tables=tuple(tables))
