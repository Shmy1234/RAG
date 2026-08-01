from typing import ClassVar

from ingest.chunking import ChunkRecord, metadata_from_chunk, section_from_headings


class FakeOrigin:
    page_no = 7


class FakeMeta:
    headings: ClassVar[list[str]] = ["Item 8", "Consolidated Statements of Operations"]
    captions: ClassVar[list[str]] = ["In millions"]
    origin = FakeOrigin()


class FakeChunk:
    text = "Total net sales | 416,161 | 391,035"
    meta = FakeMeta()


def test_section_from_headings_uses_deepest_heading():
    assert section_from_headings(["Item 8", "Balance Sheets"]) == "Balance Sheets"


def test_metadata_from_chunk_preserves_docling_context():
    metadata = metadata_from_chunk(FakeChunk())

    assert metadata["headings"] == ["Item 8", "Consolidated Statements of Operations"]
    assert metadata["captions"] == ["In millions"]
    assert metadata["docling_page_number"] == 7


def test_chunk_record_rejects_text_over_embedding_limit():
    record = ChunkRecord(
        chunk_index=0,
        text="text",
        token_count=8193,
        page_number=None,
        section=None,
        metadata={},
    )

    assert record.token_count > 8192
