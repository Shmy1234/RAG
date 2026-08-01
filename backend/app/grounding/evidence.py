import re
from collections.abc import Iterable, Sequence
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.retrieval.schemas import ChunkReference, SourcePassage

_WORD_PATTERN = re.compile(r"[a-z][a-z0-9']{3,}")
_QUERY_STOP_WORDS = {
    "about",
    "across",
    "filing",
    "filings",
    "fiscal",
    "happened",
    "latest",
    "report",
    "reported",
    "what",
    "when",
    "where",
    "which",
    "year",
    "years",
}
_GENERIC_QUERY_TERMS = {"income", "margin", "margins", "revenue", "revenues", "sales"}


class EvidenceCandidate(BaseModel):
    evidence_id: UUID = Field(default_factory=uuid4)
    chunk_id: UUID
    exact_quote: str = Field(min_length=1, max_length=600)
    citation_label: str
    location_label: str


def build_evidence_candidates(
    passages: Sequence[SourcePassage],
    query: str,
    *,
    max_chars: int = 600,
) -> list[EvidenceCandidate]:
    terms = _query_terms(query)
    if not terms:
        return []
    required_terms = terms - _GENERIC_QUERY_TERMS or terms

    candidates: list[EvidenceCandidate] = []
    seen_ids: set[UUID] = set()
    for chunk in _passage_chunks(passages):
        if chunk.chunk_id in seen_ids:
            continue
        seen_ids.add(chunk.chunk_id)
        quote = _matching_excerpt(
            chunk.text,
            terms,
            required_terms=required_terms,
            max_chars=max_chars,
        )
        if quote is None:
            continue
        candidates.append(
            EvidenceCandidate(
                chunk_id=chunk.chunk_id,
                exact_quote=quote,
                citation_label=chunk.citation_label,
                location_label=chunk.location_label,
            )
        )
    return candidates


def _query_terms(query: str) -> set[str]:
    return set(_WORD_PATTERN.findall(query.casefold())) - _QUERY_STOP_WORDS


def _passage_chunks(passages: Sequence[SourcePassage]) -> Iterable[ChunkReference]:
    for passage in passages:
        yield passage.center.chunk
        yield from passage.previous_chunks
        yield from passage.next_chunks


def _matching_excerpt(
    text: str,
    terms: set[str],
    *,
    required_terms: set[str],
    max_chars: int,
) -> str | None:
    lowered = text.casefold()
    if not any(term in lowered for term in required_terms):
        return None
    positions = [lowered.find(term) for term in terms if lowered.find(term) >= 0]
    if not positions:
        return None
    if len(text) <= max_chars:
        return text

    best_window = text[:max_chars]
    best_score = -1
    for position in positions:
        start = max(0, min(position - max_chars // 2, len(text) - max_chars))
        window = text[start : start + max_chars]
        score = sum(term in window.casefold() for term in terms)
        if score > best_score:
            best_window = window
            best_score = score
    return best_window.strip()
