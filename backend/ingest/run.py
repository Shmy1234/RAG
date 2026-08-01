"""Command-line entrypoint for Markdown filing ingestion."""

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from app.config import settings
from ingest.chunking import ChunkRecord, chunk_markdown_document
from ingest.embeddings import batch_embedding_inputs, embed_texts
from ingest.manifest import IngestDocument, load_manifest
from ingest.repository import (
    create_sessionmaker,
    document_exists,
    insert_chunks,
    replace_document,
)

DEFAULT_MARKDOWN_ROOT = Path(__file__).resolve().parents[2] / "data" / "Markdown"


@dataclass(frozen=True)
class PreparedDocument:
    document: IngestDocument
    content: str
    chunks: list[ChunkRecord]


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be greater than zero")
    return parsed


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="chunk and summarize without writes")
    mode.add_argument("--upload", action="store_true", help="embed and write to Postgres")
    parser.add_argument("--markdown-root", type=Path, default=DEFAULT_MARKDOWN_ROOT)
    parser.add_argument("--replace", action="store_true", help="replace an existing accession")
    parser.add_argument("--yes", action="store_true", help="confirm an unbounded upload")
    parser.add_argument("--limit-documents", type=_positive_int)
    parser.add_argument("--limit-chunks", type=_positive_int)
    parser.add_argument("--max-chunk-tokens", type=_positive_int, default=1200)
    parser.add_argument(
        "--embedding-batch-token-limit",
        type=_positive_int,
        default=250_000,
    )
    args = parser.parse_args(argv)
    if not args.upload:
        args.dry_run = True
    return args


def _prepare_documents(args: argparse.Namespace) -> list[PreparedDocument]:
    documents = load_manifest(args.markdown_root)
    if args.limit_documents is not None:
        documents = documents[: args.limit_documents]

    prepared: list[PreparedDocument] = []
    for document in documents:
        content = document.markdown_path.read_text(encoding="utf-8")
        chunks = chunk_markdown_document(
            document,
            embedding_model=settings.OPENAI_EMBEDDING_MODEL,
            max_tokens=args.max_chunk_tokens,
        )
        if args.limit_chunks is not None:
            chunks = chunks[: args.limit_chunks]
        prepared.append(PreparedDocument(document=document, content=content, chunks=chunks))
    return prepared


def _print_summary(prepared: list[PreparedDocument], mode: str) -> None:
    total_chunks = sum(len(item.chunks) for item in prepared)
    total_tokens = sum(chunk.token_count for item in prepared for chunk in item.chunks)
    max_tokens = max(
        (chunk.token_count for item in prepared for chunk in item.chunks),
        default=0,
    )
    print(
        f"mode={mode} documents={len(prepared)} chunks={total_chunks} "
        f"tokens={total_tokens} max_chunk_tokens={max_tokens}"
    )
    for item in prepared:
        sections = [chunk.section for chunk in item.chunks if chunk.section]
        sample = ", ".join(sections[:3]) or "(no section)"
        print(
            f"{item.document.accession_number} {item.document.ticker} "
            f"fiscal_year={item.document.fiscal_year} chunks={len(item.chunks)} "
            f"sample_sections={sample}"
        )


def _upload_documents(prepared: list[PreparedDocument], args: argparse.Namespace) -> None:
    session_factory = create_sessionmaker()
    uploaded = 0
    skipped = 0

    for item in prepared:
        with session_factory() as session:
            exists = document_exists(session, item.document.accession_number)
        if exists and not args.replace:
            print(f"skipped accession={item.document.accession_number} reason=already_ingested")
            skipped += 1
            continue

        embeddings: list[list[float]] = []
        for batch in batch_embedding_inputs(
            item.chunks,
            max_batch_tokens=args.embedding_batch_token_limit,
        ):
            embeddings.extend(
                embed_texts(
                    [chunk.text for chunk in batch],
                    model=settings.OPENAI_EMBEDDING_MODEL,
                    dimensions=settings.OPENAI_EMBEDDING_DIMENSIONS,
                )
            )

        with session_factory.begin() as session:
            if not args.replace and document_exists(session, item.document.accession_number):
                print(f"skipped accession={item.document.accession_number} reason=already_ingested")
                skipped += 1
                continue
            source_document = replace_document(session, item.document, item.content)
            insert_chunks(session, source_document, item.chunks, embeddings)
        uploaded += 1
        print(
            f"uploaded accession={item.document.accession_number} "
            f"chunks={len(item.chunks)} embeddings={len(embeddings)}"
        )

    print(f"upload_summary uploaded={uploaded} skipped={skipped}")


def run_pipeline(args: argparse.Namespace) -> int:
    prepared = _prepare_documents(args)
    _print_summary(prepared, "dry-run" if args.dry_run else "upload")

    if args.dry_run:
        return 0
    if args.limit_documents is None and not args.yes:
        print("full upload requires --yes; no OpenAI or database writes were performed")
        return 2

    _upload_documents(prepared, args)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    return run_pipeline(parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
