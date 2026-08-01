from datetime import date
from uuid import UUID, uuid4

import pytest

from app.assistant.outputs import AgentAnswer, Citation, CitationDraft, GroundedAnswer
from app.grounding.evidence import EvidenceCandidate, build_evidence_candidates
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


def test_validator_builds_server_owned_citation_metadata_from_draft():
    source = passage()
    evidence = evidence_candidate(source)
    answer = AgentAnswer(
        answer="Services revenue increased.",
        citations=[CitationDraft(evidence_id=evidence.evidence_id)],
    )

    result = GroundingValidator().validate(
        answer,
        [source],
        evidence_candidates={evidence.evidence_id: evidence},
    )

    assert result.answer == "Services revenue increased."
    assert result.citations == [
        citation().model_copy(update={"quoted_text": source.center.chunk.text})
    ]
    assert result.cited_passages[0].center.chunk.chunk_id == citation().chunk_id


def test_validator_builds_bounded_exact_excerpt_for_long_table_chunk():
    table_text = (
        "Fiscal years 2025 2024 2023 unrelated operating expense details. " * 30
        + "Product rows without matching values. " * 30
        + "Services (1), = 109,158. Services (1), = 96,169. Services (1), = 85,200. "
        + "Unrelated balance sheet details. " * 30
    )
    source = passage().model_copy(
        update={
            "center": passage().center.model_copy(
                update={"chunk": passage().center.chunk.model_copy(update={"text": table_text})}
            )
        }
    )
    answer = AgentAnswer(
        answer=(
            "Services revenue increased to $109.158 billion in 2025 from $96.169 in 2024 "
            "and $85.200 billion in 2023."
        ),
        citations=[],
    )
    evidence = build_evidence_candidates([source], "Services revenue")[0]
    answer = answer.model_copy(
        update={"citations": [CitationDraft(evidence_id=evidence.evidence_id)]}
    )

    result = GroundingValidator().validate(
        answer,
        [source],
        evidence_candidates={evidence.evidence_id: evidence},
    )

    quote = result.citations[0].quoted_text
    assert quote in table_text
    assert len(quote) <= 600
    assert "Services (1), = 109,158" in quote
    assert "85,200" in quote


def test_validator_canonicalizes_metadata_from_retrieved_chunk():
    answer = GroundedAnswer(
        answer="Services revenue increased.",
        citations=[
            citation().model_copy(
                update={"citation_label": "wrong label", "location_label": "wrong location"}
            )
        ],
    )

    result = GroundingValidator().validate(answer, [passage()])

    assert result.citations[0].citation_label == "AAPL 10-K 2025"
    assert result.citations[0].location_label == "page 42, Results"


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


def test_validator_accepts_evidence_candidate_covering_rounded_financial_values():
    source = passage().model_copy(
        update={
            "center": passage().center.model_copy(
                update={
                    "chunk": passage().center.chunk.model_copy(
                        update={
                            "text": "Services revenue was 109,158, compared with 96,169 and 85,200."
                        }
                    )
                }
            )
        }
    )
    evidence = evidence_candidate(source)
    answer = AgentAnswer(
        answer=(
            "Services revenue reached $109.2 billion in 2025, up from $96.2 billion in 2024 "
            "and $85.2 billion in 2023."
        ),
        citations=[CitationDraft(evidence_id=evidence.evidence_id)],
    )

    result = GroundingValidator().validate(
        answer,
        [source],
        evidence_candidates={evidence.evidence_id: evidence},
    )

    assert result.citations[0].quoted_text == evidence.exact_quote


def test_validator_accepts_currency_values_with_explicit_million_unit():
    source = passage().model_copy(
        update={
            "center": passage().center.model_copy(
                update={
                    "chunk": passage().center.chunk.model_copy(
                        update={"text": "Services revenue was 109,158, compared with 96,169."}
                    )
                }
            )
        }
    )
    evidence = evidence_candidate(source)
    answer = AgentAnswer(
        answer="Services revenue was $109,158 million, compared with $96,169 million.",
        citations=[CitationDraft(evidence_id=evidence.evidence_id)],
    )

    result = GroundingValidator().validate(
        answer,
        [source],
        evidence_candidates={evidence.evidence_id: evidence},
    )

    assert result.citations[0].quoted_text == evidence.exact_quote


def test_validator_rejects_financial_values_reversed_from_evidence_order():
    source = passage().model_copy(
        update={
            "center": passage().center.model_copy(
                update={
                    "chunk": passage().center.chunk.model_copy(
                        update={"text": "Services revenue was 109,158, compared with 96,169."}
                    )
                }
            )
        }
    )
    evidence = evidence_candidate(source)
    answer = AgentAnswer(
        answer="Services revenue decreased to $96,169 million from $109,158 million.",
        citations=[CitationDraft(evidence_id=evidence.evidence_id)],
    )

    with pytest.raises(GroundingError, match="order"):
        GroundingValidator().validate(
            answer,
            [source],
            evidence_candidates={evidence.evidence_id: evidence},
        )


def test_validator_rejects_irrelevant_evidence_for_services_claim():
    source = passage().model_copy(
        update={
            "center": passage().center.model_copy(
                update={
                    "chunk": passage().center.chunk.model_copy(
                        update={"text": "Research and development expense was 29,915."}
                    )
                }
            )
        }
    )
    evidence = evidence_candidate(source)
    answer = AgentAnswer(
        answer="Services revenue reached $109.2 billion.",
        citations=[CitationDraft(evidence_id=evidence.evidence_id)],
    )

    with pytest.raises(GroundingError, match="support"):
        GroundingValidator().validate(
            answer,
            [source],
            evidence_candidates={evidence.evidence_id: evidence},
        )


def test_validator_rejects_financial_figure_missing_from_evidence():
    source = passage().model_copy(
        update={
            "center": passage().center.model_copy(
                update={
                    "chunk": passage().center.chunk.model_copy(
                        update={"text": "Services revenue was 109,158."}
                    )
                }
            )
        }
    )
    evidence = evidence_candidate(source)
    answer = AgentAnswer(
        answer="Services revenue reached $999.9 billion.",
        citations=[CitationDraft(evidence_id=evidence.evidence_id)],
    )

    with pytest.raises(GroundingError, match="number"):
        GroundingValidator().validate(
            answer,
            [source],
            evidence_candidates={evidence.evidence_id: evidence},
        )


def test_validator_removes_extra_citation_that_supports_no_financial_figure():
    supported_source = passage().model_copy(
        update={
            "center": passage().center.model_copy(
                update={
                    "chunk": passage().center.chunk.model_copy(
                        update={"text": "Services revenue was 109,158, compared with 96,169 and 85,200."}
                    )
                }
            )
        }
    )
    introduction_source = passage().model_copy(
        update={
            "center": passage().center.model_copy(
                update={
                    "chunk": passage().center.chunk.model_copy(
                        update={
                            "chunk_id": UUID("00000000-0000-0000-0000-000000000002"),
                            "text": "The following table shows disaggregated Services net sales.",
                        }
                    )
                }
            )
        }
    )
    supported = evidence_candidate(supported_source)
    introduction = evidence_candidate(introduction_source)
    answer = AgentAnswer(
        answer="Services revenue reached $109.2 billion from $96.2 billion and $85.2 billion.",
        citations=[
            CitationDraft(evidence_id=supported.evidence_id),
            CitationDraft(evidence_id=introduction.evidence_id),
        ],
    )

    result = GroundingValidator().validate(
        answer,
        [supported_source, introduction_source],
        evidence_candidates={
            supported.evidence_id: supported,
            introduction.evidence_id: introduction,
        },
    )

    assert [citation.chunk_id for citation in result.citations] == [supported.chunk_id]


def test_validator_rejects_evidence_id_not_registered_for_run():
    answer = AgentAnswer(
        answer="Services revenue increased.",
        citations=[CitationDraft(evidence_id=uuid4())],
    )

    with pytest.raises(GroundingError, match="evidence"):
        GroundingValidator().validate(answer, [passage()], evidence_candidates={})


def test_validator_rejects_wrong_selected_evidence_even_when_support_exists_in_pool():
    supported_source = passage().model_copy(
        update={
            "center": passage().center.model_copy(
                update={
                    "chunk": passage().center.chunk.model_copy(
                        update={"text": "Services revenue was 109,158, compared with 96,169 and 85,200."}
                    )
                }
            )
        }
    )
    wrong_source = passage().model_copy(
        update={
            "center": passage().center.model_copy(
                update={
                    "chunk": passage().center.chunk.model_copy(
                        update={
                            "chunk_id": UUID("00000000-0000-0000-0000-000000000002"),
                            "text": "Services are described in the filing introduction.",
                        }
                    )
                }
            )
        }
    )
    supported = evidence_candidate(supported_source)
    wrong = evidence_candidate(wrong_source)
    answer = AgentAnswer(
        answer="Services revenue reached $109.2 billion from $96.2 billion and $85.2 billion.",
        citations=[CitationDraft(evidence_id=wrong.evidence_id)],
    )

    with pytest.raises(GroundingError, match="support"):
        GroundingValidator().validate(
            answer,
            [wrong_source, supported_source],
            evidence_candidates={wrong.evidence_id: wrong, supported.evidence_id: supported},
        )


def test_validator_rejects_answer_with_one_supported_and_one_unsupported_claim():
    source = passage()
    evidence = evidence_candidate(source)
    answer = AgentAnswer(
        answer=(
            "Services revenue increased 14% in fiscal 2025. "
            "Wearables revenue increased 30% in fiscal 2025."
        ),
        citations=[CitationDraft(evidence_id=evidence.evidence_id)],
    )

    with pytest.raises(GroundingError, match="claim"):
        GroundingValidator().validate(
            answer,
            [source],
            evidence_candidates={evidence.evidence_id: evidence},
        )


def evidence_candidate(source: SourcePassage) -> EvidenceCandidate:
    chunk = source.center.chunk
    return EvidenceCandidate(
        evidence_id=uuid4(),
        chunk_id=chunk.chunk_id,
        exact_quote=chunk.text,
        citation_label=chunk.citation_label,
        location_label=chunk.location_label,
    )
