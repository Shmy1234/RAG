from datetime import date
from uuid import UUID

from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.schemas import ChunkReference, RankedChunk


def chunk(number: int) -> ChunkReference:
    return ChunkReference(
        chunk_id=UUID(f"00000000-0000-0000-0000-{number:012d}"),
        document_id=UUID("00000000-0000-0000-0000-999999999999"),
        chunk_index=number,
        text=f"chunk {number}",
        page_number=None,
        section=None,
        ticker="AAPL",
        company_name="Apple Inc.",
        filing_type="10-K",
        filing_date=date(2025, 10, 31),
        fiscal_year=2025,
        accession_number="0000320193-25-000079",
        source_url="https://www.sec.gov/example",
    )


def ranked(number: int, rank: int, source: str, score: float) -> RankedChunk:
    return RankedChunk(chunk=chunk(number), rank=rank, source=source, score=score)


def test_rrf_rewards_chunks_found_by_both_retrievers():
    fused = reciprocal_rank_fusion(
        [
            [ranked(1, 1, "semantic", 0.9), ranked(2, 2, "semantic", 0.8)],
            [ranked(2, 1, "full_text", 3.0), ranked(3, 2, "full_text", 2.0)],
        ],
        k=60,
    )

    assert [item.chunk.chunk_id for item in fused][:2] == [
        UUID("00000000-0000-0000-0000-000000000002"),
        UUID("00000000-0000-0000-0000-000000000001"),
    ]
    assert fused[0].semantic_rank == 2
    assert fused[0].full_text_rank == 1
    assert fused[0].semantic_score == 0.8
    assert fused[0].full_text_score == 3.0


def test_rrf_preserves_first_seen_order_for_equal_scores():
    fused = reciprocal_rank_fusion(
        [[ranked(1, 1, "semantic", 0.9)], [ranked(2, 1, "full_text", 3.0)]],
        k=60,
    )

    assert [item.chunk.chunk_index for item in fused] == [1, 2]


def test_rrf_rejects_non_positive_k():
    try:
        reciprocal_rank_fusion([], k=0)
    except ValueError as exc:
        assert "k" in str(exc)
    else:
        raise AssertionError("expected ValueError")
