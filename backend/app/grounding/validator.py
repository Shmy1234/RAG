import re
from collections.abc import Sequence
from uuid import UUID

from app.assistant.outputs import AgentAnswer, Citation, GroundedAnswer
from app.grounding.evidence import EvidenceCandidate
from app.retrieval.schemas import ChunkReference, SourcePassage

_WORD_PATTERN = re.compile(r"[a-z][a-z0-9']{3,}")
_FINANCIAL_NUMBER_PATTERN = re.compile(
    r"(?P<currency>\$)?(?P<number>\d[\d,]*(?:\.\d+)?)\s*(?P<unit>billion|million|%)?",
    re.IGNORECASE,
)
_CLAIM_STOP_WORDS = {
    "apple",
    "billion",
    "company",
    "compared",
    "decreased",
    "filing",
    "fiscal",
    "increased",
    "latest",
    "million",
    "reported",
    "reached",
    "revenue",
    "total",
    "year",
    "years",
}
_SENTENCE_BOUNDARY_PATTERN = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")


class GroundingError(ValueError):
    """Raised when an answer cannot be tied to the current retrieved evidence."""


class GroundingValidator:
    def validate(
        self,
        answer: AgentAnswer | GroundedAnswer,
        passages: Sequence[SourcePassage],
        *,
        evidence_candidates: dict[UUID, EvidenceCandidate] | None = None,
    ) -> GroundedAnswer:
        chunks = self._chunk_index(passages)
        if not answer.citations:
            if self._is_insufficient_evidence(answer.answer):
                return GroundedAnswer(answer=answer.answer)
            raise GroundingError("answer must include at least one citation")

        if isinstance(answer, AgentAnswer):
            return self._validate_agent_answer(answer, passages, evidence_candidates or {})

        cited_chunks: list[ChunkReference] = []
        canonical_citations: list[Citation] = []
        seen_ids: set[UUID] = set()
        for citation in answer.citations:
            chunk_id = citation.chunk_id
            chunk = chunks.get(chunk_id)
            if chunk is None:
                raise GroundingError("citation refers to a chunk that was not retrieved")
            quoted_text = citation.quoted_text
            if quoted_text not in chunk.text:
                raise GroundingError("citation quote does not appear in the retrieved chunk")
            canonical_citations.append(
                Citation(
                    chunk_id=chunk_id,
                    citation_index=len(canonical_citations),
                    quoted_text=quoted_text,
                    citation_label=chunk.citation_label,
                    location_label=chunk.location_label,
                )
            )
            if chunk.chunk_id not in seen_ids:
                cited_chunks.append(chunk)
                seen_ids.add(chunk.chunk_id)

        return GroundedAnswer(
            answer=answer.answer,
            citations=canonical_citations,
            cited_passages=self._passages_for_chunks(passages, cited_chunks),
        )

    def _validate_agent_answer(
        self,
        answer: AgentAnswer,
        passages: Sequence[SourcePassage],
        evidence_candidates: dict[UUID, EvidenceCandidate],
    ) -> GroundedAnswer:
        chunks = self._chunk_index(passages)
        selected: list[EvidenceCandidate] = []
        for citation in answer.citations:
            evidence = evidence_candidates.get(citation.evidence_id)
            if evidence is None:
                raise GroundingError("citation refers to evidence that was not registered for this run")
            selected.append(evidence)

        relevant: list[EvidenceCandidate] = []
        for evidence in selected:
            chunk = chunks.get(evidence.chunk_id)
            if chunk is None:
                continue
            if evidence.exact_quote not in chunk.text:
                raise GroundingError("registered evidence does not appear in the retrieved chunk")
            try:
                self._validate_keyword_support(answer.answer, evidence.exact_quote)
            except GroundingError:
                continue
            relevant.append(evidence)

        self._validate_claims(answer.answer, relevant)

        required_numbers = self._financial_numbers(answer.answer)
        chosen = self._choose_evidence(relevant, required_numbers)
        if not chosen:
            detail = "a financial number" if required_numbers else "the answer"
            raise GroundingError(f"no registered evidence supports {detail}")
        chosen_quotes = [item.exact_quote for item in chosen]
        self._validate_financial_numbers(answer.answer, chosen_quotes)
        self._validate_financial_number_order(answer.answer, chosen_quotes)

        citations: list[Citation] = []
        cited_chunks: list[ChunkReference] = []
        seen_chunks: set[UUID] = set()
        for evidence in chosen:
            chunk = chunks[evidence.chunk_id]
            citations.append(
                Citation(
                    chunk_id=chunk.chunk_id,
                    citation_index=len(citations),
                    quoted_text=evidence.exact_quote,
                    citation_label=chunk.citation_label,
                    location_label=chunk.location_label,
                )
            )
            if chunk.chunk_id not in seen_chunks:
                cited_chunks.append(chunk)
                seen_chunks.add(chunk.chunk_id)
        return GroundedAnswer(
            answer=answer.answer,
            citations=citations,
            cited_passages=self._passages_for_chunks(passages, cited_chunks),
        )

    @classmethod
    def _validate_claims(
        cls,
        answer: str,
        evidence: Sequence[EvidenceCandidate],
    ) -> None:
        quotes = [item.exact_quote for item in evidence]
        for raw_claim in _SENTENCE_BOUNDARY_PATTERN.split(answer):
            claim = raw_claim.strip()
            if not claim:
                continue
            for quote in quotes:
                try:
                    cls._validate_keyword_support(claim, quote)
                except GroundingError:
                    continue
                break
            else:
                raise GroundingError("selected evidence does not support claim keywords")
            cls._validate_financial_numbers(claim, quotes)
            cls._validate_financial_number_order(claim, quotes)

    @classmethod
    def _choose_evidence(
        cls,
        candidates: Sequence[EvidenceCandidate],
        required_numbers: Sequence[tuple[float, str | None]],
    ) -> list[EvidenceCandidate]:
        if not required_numbers:
            return list(candidates[:1])

        missing = set(range(len(required_numbers)))
        chosen: list[EvidenceCandidate] = []
        while missing:
            best = None
            best_coverage: set[int] = set()
            for candidate in candidates:
                if candidate in chosen:
                    continue
                coverage = {
                    index
                    for index in missing
                    if cls._quote_supports_number(candidate.exact_quote, [required_numbers[index]])
                }
                if len(coverage) > len(best_coverage):
                    best = candidate
                    best_coverage = coverage
            if best is None:
                break
            chosen.append(best)
            missing -= best_coverage
        return chosen if not missing else []

    @staticmethod
    def _chunk_index(passages: Sequence[SourcePassage]) -> dict[UUID, ChunkReference]:
        chunks: dict[UUID, ChunkReference] = {}
        for passage in passages:
            chunks[passage.center.chunk.chunk_id] = passage.center.chunk
            for chunk in passage.previous_chunks + passage.next_chunks:
                chunks[chunk.chunk_id] = chunk
        return chunks

    @staticmethod
    def _passages_for_chunks(
        passages: Sequence[SourcePassage],
        cited_chunks: Sequence[ChunkReference],
    ) -> list[SourcePassage]:
        cited_ids = {chunk.chunk_id for chunk in cited_chunks}
        return [
            passage
            for passage in passages
            if passage.center.chunk.chunk_id in cited_ids
            or any(chunk.chunk_id in cited_ids for chunk in passage.previous_chunks)
            or any(chunk.chunk_id in cited_ids for chunk in passage.next_chunks)
        ]

    @staticmethod
    def _is_insufficient_evidence(answer: str) -> bool:
        normalized = answer.casefold()
        return any(
            phrase in normalized
            for phrase in (
                "not enough evidence",
                "insufficient evidence",
                "corpus does not contain enough",
                "cannot determine from the available filings",
            )
        )

    @staticmethod
    def _validate_keyword_support(answer: str, quote: str) -> None:
        answer_terms = set(_WORD_PATTERN.findall(answer.casefold())) - _CLAIM_STOP_WORDS
        quote_terms = set(_WORD_PATTERN.findall(quote.casefold()))
        if answer_terms and not answer_terms.intersection(quote_terms):
            raise GroundingError("citation evidence does not support the answer keywords")

    @classmethod
    def _validate_financial_numbers(cls, answer: str, quotes: Sequence[str]) -> None:
        required = cls._financial_numbers(answer)
        if not required:
            return
        available = cls._financial_numbers(" ".join(quotes), include_plain_thousands=True)
        for value, unit in required:
            if not any(cls._numbers_match(value, unit, candidate, candidate_unit) for candidate, candidate_unit in available):
                raise GroundingError("answer contains a financial number not supported by citation evidence")

    @classmethod
    def _validate_financial_number_order(cls, answer: str, quotes: Sequence[str]) -> None:
        required = cls._financial_numbers(answer)
        if len(required) < 2:
            return
        available = cls._financial_numbers(" ".join(quotes), include_plain_thousands=True)
        position = 0
        for required_value, required_unit in required:
            for index in range(position, len(available)):
                candidate_value, candidate_unit = available[index]
                if cls._numbers_match(
                    required_value,
                    required_unit,
                    candidate_value,
                    candidate_unit,
                ):
                    position = index + 1
                    break
            else:
                raise GroundingError(
                    "financial values must preserve the order shown in the citation evidence"
                )

    @staticmethod
    def _financial_numbers(
        text: str,
        *,
        include_plain_thousands: bool = False,
    ) -> list[tuple[float, str | None]]:
        values: list[tuple[float, str | None]] = []
        for match in _FINANCIAL_NUMBER_PATTERN.finditer(text):
            raw = match.group("number")
            unit = match.group("unit")
            currency = match.group("currency")
            has_comma = "," in raw
            if not (currency or unit or (include_plain_thousands and has_comma)):
                continue
            value = float(raw.replace(",", ""))
            normalized_unit = unit.casefold() if unit else None
            if normalized_unit == "billion":
                value *= 1000
                normalized_unit = "million"
            elif currency and normalized_unit is None:
                normalized_unit = "currency"
            values.append((value, normalized_unit))
        return values

    @staticmethod
    def _numbers_match(
        required: float,
        required_unit: str | None,
        available: float,
        available_unit: str | None,
    ) -> bool:
        if required_unit == "%" or available_unit == "%":
            return required_unit == available_unit and abs(required - available) < 0.05
        if required_unit == "currency" and available >= 1000:
            required *= 1000
        if available_unit == "billion":
            available *= 1000
        difference = abs(required - available)
        return difference <= max(1, required * 0.005)

    @classmethod
    def _quote_supports_number(
        cls,
        quote: str,
        required_numbers: Sequence[tuple[float, str | None]],
    ) -> bool:
        available = cls._financial_numbers(quote, include_plain_thousands=True)
        return any(
            cls._numbers_match(required, unit, candidate, candidate_unit)
            for required, unit in required_numbers
            for candidate, candidate_unit in available
        )
