"""Docling conversion and structure-aware retrieval chunking."""

from dataclasses import asdict, dataclass
from typing import Any

import tiktoken
from docling.chunking import HierarchicalChunker, HybridChunker
from docling.document_converter import DocumentConverter
from docling_core.transforms.chunker.tokenizer.openai import OpenAITokenizer

from ingest.manifest import IngestDocument
from ingest.models import ExtractedDocument, ExtractedTable

OPENAI_MAX_INPUT_TOKENS = 8192


@dataclass(frozen=True)
class ChunkRecord:
    chunk_index: int
    text: str
    token_count: int
    page_number: int | None
    section: str | None
    metadata: dict[str, Any]
    kind: str = "narrative"
    table_index: int | None = None
    row_start: int | None = None
    row_end: int | None = None


def build_openai_tokenizer(model: str, max_tokens: int) -> OpenAITokenizer:
    return OpenAITokenizer(
        tokenizer=tiktoken.encoding_for_model(model),
        max_tokens=max_tokens,
    )


def section_from_headings(headings: list[str] | None) -> str | None:
    if not headings:
        return None
    return headings[-1]


def metadata_from_chunk(chunk: Any) -> dict[str, Any]:
    meta = getattr(chunk, "meta", None)
    headings = list(getattr(meta, "headings", None) or [])
    captions = list(getattr(meta, "captions", None) or [])
    origin = getattr(meta, "origin", None)
    page_number = getattr(origin, "page_no", None)

    metadata: dict[str, Any] = {
        "headings": headings,
        "captions": captions,
    }
    if page_number is not None:
        metadata["docling_page_number"] = page_number
    return metadata


def chunk_markdown_document(
    document: IngestDocument,
    embedding_model: str,
    max_tokens: int = 1200,
) -> list[ChunkRecord]:
    tokenizer = build_openai_tokenizer(embedding_model, max_tokens)
    dl_doc = DocumentConverter().convert(document.markdown_path).document
    hierarchical_chunks = list(HierarchicalChunker().chunk(dl_doc=dl_doc))
    hybrid_chunker = HybridChunker(tokenizer=tokenizer, merge_peers=True)
    chunks: list[ChunkRecord] = []

    for chunk_index, chunk in enumerate(hybrid_chunker.chunk(dl_doc=dl_doc)):
        text = hybrid_chunker.contextualize(chunk)
        if not text.strip():
            continue
        token_count = tokenizer.count_tokens(text)
        if token_count > OPENAI_MAX_INPUT_TOKENS:
            raise ValueError(
                f"Chunk {chunk_index} in {document.markdown_path} has {token_count} tokens; "
                f"OpenAI's maximum is {OPENAI_MAX_INPUT_TOKENS}"
            )

        metadata = metadata_from_chunk(chunk)
        metadata["hierarchical_chunk_count"] = len(hierarchical_chunks)
        raw_text = getattr(chunk, "text", text)
        if raw_text != text:
            metadata["raw_text"] = raw_text
        headings = metadata["headings"]
        chunks.append(
            ChunkRecord(
                chunk_index=len(chunks),
                text=text,
                token_count=token_count,
                page_number=metadata.get("docling_page_number"),
                section=section_from_headings(headings),
                metadata=metadata,
            )
        )

    return chunks


def _table_row_text(table: ExtractedTable, row_index: int) -> str:
    row = table.rows[row_index]
    parts = []
    if table.section_path:
        parts.append(f"Section: {' > '.join(table.section_path)}")
    if table.title:
        parts.append(f"Table: {table.title}")
    if table.units:
        parts.append(f"Units: {table.units}")
    parts.append(f"Headers: {' | '.join(table.headers)}")
    parts.append(f"Row: {' | '.join((row.label, *row.values))}")
    return "\n".join(parts)


def chunk_extracted_document(
    document: ExtractedDocument,
    embedding_model: str,
    max_tokens: int = 1200,
) -> list[ChunkRecord]:
    """Chunk canonical blocks without reparsing derived Markdown."""
    tokenizer = build_openai_tokenizer(embedding_model, max_tokens)
    encoding = tiktoken.encoding_for_model(embedding_model)
    tables = {table.table_index: table for table in document.tables}
    chunks: list[ChunkRecord] = []

    for block in document.blocks:
        if block.kind == "text" and block.text:
            heading = block.section_path[-1] if block.section_path else None
            prefix = f"Section: {heading}\n" if heading else ""
            prefix_tokens = encoding.encode(prefix)
            available_tokens = max_tokens - len(prefix_tokens)
            if available_tokens < 1:
                raise ValueError(f"Section heading exceeds {max_tokens} tokens: {heading}")
            body_tokens = encoding.encode(block.text)
            for offset in range(0, len(body_tokens), available_tokens):
                text = prefix + encoding.decode(body_tokens[offset : offset + available_tokens])
                chunks.append(
                    ChunkRecord(
                        chunk_index=len(chunks),
                        text=text,
                        token_count=tokenizer.count_tokens(text),
                        page_number=None,
                        section=heading,
                        metadata={
                            "section_path": list(block.section_path),
                            "source_locator": asdict(block.source_locator),
                        },
                        kind="narrative",
                    )
                )
            continue
        if block.kind != "table" or block.table_index is None:
            continue
        table = tables[block.table_index]
        for row_index, row in enumerate(table.rows):
            text = _table_row_text(table, row_index)
            token_count = tokenizer.count_tokens(text)
            if token_count > max_tokens:
                raise ValueError(
                    f"Table {table.table_index} row {row_index} exceeds {max_tokens} tokens"
                )
            chunks.append(
                ChunkRecord(
                    chunk_index=len(chunks),
                    text=text,
                    token_count=token_count,
                    page_number=None,
                    section=table.section_path[-1] if table.section_path else None,
                    metadata={
                        "headers": list(table.headers),
                        "row_labels": [row.label],
                        "source_locator": asdict(table.source_locator),
                    },
                    kind="table",
                    table_index=table.table_index,
                    row_start=row_index,
                    row_end=row_index,
                )
            )
    return chunks
