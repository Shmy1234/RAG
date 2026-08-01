"""Docling conversion and structure-aware retrieval chunking."""

from dataclasses import dataclass
from typing import Any

import tiktoken
from docling.chunking import HierarchicalChunker, HybridChunker
from docling.document_converter import DocumentConverter
from docling_core.transforms.chunker.tokenizer.openai import OpenAITokenizer

from ingest.manifest import IngestDocument

OPENAI_MAX_INPUT_TOKENS = 8192


@dataclass(frozen=True)
class ChunkRecord:
    chunk_index: int
    text: str
    token_count: int
    page_number: int | None
    section: str | None
    metadata: dict[str, Any]


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
