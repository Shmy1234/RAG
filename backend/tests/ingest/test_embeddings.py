from ingest.chunking import ChunkRecord
from ingest.embeddings import (
    batch_embedding_inputs,
    validate_embedding_dimensions,
)


def chunk(index: int, token_count: int) -> ChunkRecord:
    return ChunkRecord(
        chunk_index=index,
        text=f"chunk {index}",
        token_count=token_count,
        page_number=None,
        section=None,
        metadata={},
    )


def test_batch_embedding_inputs_respects_total_token_budget():
    batches = batch_embedding_inputs(
        [chunk(0, 700), chunk(1, 700), chunk(2, 700)],
        max_batch_tokens=1400,
        max_batch_items=10,
    )

    assert [[item.chunk_index for item in batch] for batch in batches] == [[0, 1], [2]]


def test_validate_embedding_dimensions_rejects_wrong_vector_size():
    try:
        validate_embedding_dimensions([[0.1, 0.2]], dimensions=1536)
    except ValueError as exc:
        assert "1536" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_batch_embedding_inputs_rejects_chunk_over_openai_limit():
    try:
        batch_embedding_inputs([chunk(0, 8193)])
    except ValueError as exc:
        assert "8192" in str(exc)
    else:
        raise AssertionError("expected ValueError")
