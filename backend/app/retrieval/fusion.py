from collections.abc import Sequence

from app.retrieval.schemas import FusedChunk, RankedChunk


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[RankedChunk]],
    *,
    k: int = 60,
) -> list[FusedChunk]:
    if k <= 0:
        raise ValueError("k must be greater than zero")

    fused: dict[str, FusedChunk] = {}
    first_seen: dict[str, int] = {}
    seen_counter = 0

    for ranking in rankings:
        for item in ranking:
            key = str(item.chunk.chunk_id)
            if key not in fused:
                seen_counter += 1
                first_seen[key] = seen_counter
                fused[key] = FusedChunk(chunk=item.chunk, rrf_score=0.0)

            current = fused[key]
            current.rrf_score += 1.0 / (k + item.rank)
            if item.source == "semantic":
                current.semantic_rank = item.rank
                current.semantic_score = item.score
            else:
                current.full_text_rank = item.rank
                current.full_text_score = item.score

    return sorted(
        fused.values(),
        key=lambda item: (-item.rrf_score, first_seen[str(item.chunk.chunk_id)]),
    )
