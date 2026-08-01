from datetime import date
from uuid import UUID, uuid4

import pytest

from app.assistant.outputs import Citation, GroundedAnswer
from app.grounding.validator import GroundingError, GroundingValidator
from app.retrieval.schemas import SourcePassage


def passage() -> SourcePassage:
    from app.retrieval.schemas import ChunkReference, FusedChunk

    chunk = ChunkReference(
        chunk_id=UUID("00000000-0000-0000-0000-000000000001"),
        document_id=uuid4(),
        chunk_index=1,
        text="Services revenue increased 14% in fiscal 2025.",
        page_number=42,
        section="Results",
        ticker="AAPL",
        company_name="Apple Inc.",
        filing_type="10-K",
        filing_date=date(2025, 10, 31),
        fiscal_year=2025,
        accession_number="0000320193-25-000079",
        source_url="https://www.sec.gov/example",
    )
    return SourcePassage(center=FusedChunk(chunk=chunk, rrf_score=1.0))


def citation() -> Citation:
    chunk = passage().center.chunk
    return Citation(
        chunk_id=chunk.chunk_id,
        citation_index=0,
        quoted_text="Services revenue increased 14% in fiscal 2025.",
        citation_label=chunk.citation_label,
        location_label=chunk.location_label,
    )


def test_validator_accepts_citation_matching_retrieved_text():
    answer = GroundedAnswer(answer="Services revenue increased.", citations=[citation()])

    result = GroundingValidator().validate(answer, [passage()])

    assert result.cited_passages[0].center.chunk.chunk_id == citation().chunk_id


def test_validator_rejects_citation_for_unretrieved_chunk():
    answer = GroundedAnswer(
        answer="Unsupported.",
        citations=[citation().model_copy(update={"chunk_id": uuid4()})],
    )

    with pytest.raises(GroundingError, match="retrieved"):
        GroundingValidator().validate(answer, [passage()])


def test_validator_rejects_quote_not_present_in_retrieved_text():
    answer = GroundedAnswer(
        answer="Unsupported.",
        citations=[citation().model_copy(update={"quoted_text": "made-up figure"})],
    )

    with pytest.raises(GroundingError, match="quote"):
        GroundingValidator().validate(answer, [passage()])


def test_validator_requires_citation_for_factual_answer():
    with pytest.raises(GroundingError, match="citation"):
        GroundingValidator().validate(
            GroundedAnswer(answer="Services revenue increased."),
            [passage()],
        )


def test_validator_allows_explicit_insufficient_evidence_answer_without_citation():
    answer = GroundedAnswer(answer="The corpus does not contain enough evidence to answer this.")

    assert GroundingValidator().validate(answer, [passage()]) == answer
