from ingest.chunking import chunk_extracted_document
from ingest.models import DocumentBlock, ExtractedDocument
from ingest.sec_html import extract_sec_html
from ingest.serialization import (
    export_to_markdown,
    extracted_document_dict,
    load_extracted_document,
)

SOURCE = """
<html><body>
  <div>Item 7. Management's Discussion and Analysis</div>
  <div>Segment Operating Performance</div>
  <p>The following table shows net sales (dollars in millions):</p>
  <table id="segments">
    <tr><td colspan="3"></td><td colspan="3">2024</td><td colspan="3">2023</td></tr>
    <tr><td colspan="3">Americas</td><td>$</td><td>167,045</td><td></td><td>$</td><td>162,560</td><td></td></tr>
    <tr><td colspan="3">Europe</td><td>$</td><td>101,328</td><td></td><td>$</td><td>94,294</td><td></td></tr>
  </table>
</body></html>
"""


def test_structured_document_serializes_clean_logical_markdown():
    document = extract_sec_html(SOURCE)

    markdown = export_to_markdown(document)
    payload = extracted_document_dict(document)

    assert "| Segment | 2024 | 2023 |" in markdown
    assert "| Americas | $167,045 | $162,560 |" in markdown
    assert "Americas | Americas" not in markdown
    assert payload["extraction_version"] == "sec-html-v1"
    assert payload["tables"][0]["source_locator"]["html_id"] == "segments"


def test_table_chunks_repeat_context_and_keep_rows_intact():
    document = extract_sec_html(SOURCE)

    chunks = chunk_extracted_document(
        document,
        embedding_model="text-embedding-3-small",
        max_tokens=80,
    )
    table_chunks = [chunk for chunk in chunks if chunk.kind == "table"]

    assert table_chunks
    assert all("Headers: Segment | 2024 | 2023" in chunk.text for chunk in table_chunks)
    assert [chunk.metadata["row_labels"] for chunk in table_chunks] == [
        ["Americas"],
        ["Europe"],
    ]
    assert all(chunk.row_start == chunk.row_end for chunk in table_chunks)
    assert all(chunk.token_count <= 80 for chunk in table_chunks)


def test_structured_document_round_trips_from_json_dict():
    original = extract_sec_html(SOURCE)

    restored = load_extracted_document(extracted_document_dict(original))

    assert restored == original


def test_long_narrative_block_is_split_without_being_dropped():
    document = ExtractedDocument(
        blocks=(
            DocumentBlock(
                block_index=0,
                kind="text",
                section_path=("Item 1",),
                text=" ".join(f"word{index}" for index in range(80)),
            ),
        ),
        tables=(),
    )

    chunks = chunk_extracted_document(
        document,
        embedding_model="text-embedding-3-small",
        max_tokens=20,
    )

    assert len(chunks) > 1
    assert all(chunk.token_count <= 20 for chunk in chunks)
    assert "word0" in chunks[0].text
    assert "word79" in chunks[-1].text
