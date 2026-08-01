import asyncio
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

from pydantic_ai.models.test import TestModel

from app.assistant.agent import (
    agent_usage_limits,
    document_agent,
    prepare_retrieval_tool,
    read_chunk,
    read_surrounding_chunks,
    search_filings,
)
from app.assistant.deps import DocumentAgentDeps
from app.assistant.outputs import AgentAnswer, CitationDraft
from app.grounding.evidence import EvidenceCandidate
from app.grounding.validator import GroundingValidator
from app.retrieval.schemas import ChunkReference, RetrievalFilters, SourcePassage


def chunk() -> ChunkReference:
    return ChunkReference(
        chunk_id=UUID("00000000-0000-0000-0000-000000000001"),
        document_id=uuid4(),
        chunk_index=1,
        text="Services revenue increased.",
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


class FakeRetriever:
    def __init__(self, passages=None):
        self.filters = None
        self.retrieve_calls = 0
        self.passages = passages if passages is not None else [
            SourcePassage(center={"chunk": chunk(), "rrf_score": 1.0})
        ]

    async def retrieve(self, query: str, *, top_k: int = 5, filters=None, **kwargs):
        assert query
        assert top_k == 5
        self.retrieve_calls += 1
        self.filters = filters
        return self.passages

    async def read_chunk(self, chunk_id):
        return chunk()

    async def read_surrounding_chunks(self, chunk_id, *, window=1):
        return {"previous_chunks": [], "next_chunks": []}


class FakeValidator:
    def validate(self, answer, passages, *, evidence_candidates=None):
        return answer


def test_document_agent_has_production_model():
    assert document_agent.model is not None


def test_document_agent_returns_typed_output_and_exposes_search_tool():
    evidence = candidate(chunk())
    expected = {
        "answer": "Services revenue increased.",
        "citations": [
            {
                "evidence_id": str(evidence.evidence_id),
            }
        ],
    }
    retriever = FakeRetriever()
    deps = DocumentAgentDeps(
        user_id=uuid4(),
        thread_id=uuid4(),
        retriever=retriever,
        grounding_validator=FakeValidator(),
        retrieval_filters=RetrievalFilters(
            tickers=("AAPL",),
            filing_types=("10-K",),
            fiscal_years=(2025,),
        ),
    )
    deps.evidence_candidates[evidence.evidence_id] = evidence
    deps.retrieval_completed = True

    result = asyncio.run(
        document_agent.run(
            "Find Services revenue",
            deps=deps,
            model=TestModel(
                custom_output_args=expected,
            ),
        )
    )

    assert isinstance(result.output, AgentAnswer)
    assert isinstance(result.output.citations[0], CitationDraft)


def test_agent_usage_limits_are_small_and_bound_tool_calls():
    limits = agent_usage_limits()

    assert limits.request_limit == 4
    assert limits.tool_calls_limit == 6


def test_retrieval_tools_are_hidden_after_initial_search():
    deps = agent_deps(FakeRetriever())
    ctx = SimpleNamespace(deps=deps)
    tool_definition = object()

    assert prepare_retrieval_tool(ctx, tool_definition) is tool_definition

    deps.retrieval_completed = True

    assert prepare_retrieval_tool(ctx, tool_definition) is None


def test_agent_instructions_keep_structured_citations_out_of_answer_text():
    instructions = (Path(__file__).parents[2] / "app/assistant/instructions.md").read_text()

    assert "Do not put chunk ids or citation notation in the answer text" in instructions
    assert "Cite only evidence ids returned by the tools" in instructions
    assert "Do not cite chunk ids" in instructions
    assert "Do not reread a chunk that already has an evidence candidate" in instructions


def test_search_filings_caches_identical_searches():
    retriever = FakeRetriever()
    deps = agent_deps(retriever)
    ctx = SimpleNamespace(deps=deps)

    first = asyncio.run(search_filings(ctx, "Services revenue"))
    second = asyncio.run(search_filings(ctx, "  services REVENUE  "))

    assert first == second
    assert retriever.retrieve_calls == 1
    assert len(deps.retrieved_passages) == 1
    assert first[0].evidence_id in deps.evidence_candidates
    assert first[0].exact_quote == chunk().text
    assert retriever.filters == RetrievalFilters(tickers=("AAPL",))


def test_read_chunk_reuses_evidence_id_registered_by_search():
    deps = agent_deps(FakeRetriever())
    ctx = SimpleNamespace(deps=deps)
    searched = asyncio.run(search_filings(ctx, "Services revenue"))

    reread = asyncio.run(read_chunk(ctx, chunk().chunk_id))

    assert reread[0].evidence_id == searched[0].evidence_id
    assert len(deps.evidence_candidates) == 1


def test_search_filings_returns_terminal_message_when_no_passages_match():
    deps = agent_deps(FakeRetriever(passages=[]))

    result = asyncio.run(search_filings(SimpleNamespace(deps=deps), "No match"))

    assert result == "No matching filing passages were found. Stop searching and report insufficient evidence."


def test_read_chunk_registers_chunk_as_trusted_evidence():
    deps = agent_deps(FakeRetriever())
    deps.evidence_query = "Services revenue"
    retrieved = asyncio.run(read_chunk(SimpleNamespace(deps=deps), chunk().chunk_id))
    answer = AgentAnswer(
        answer="Services revenue increased.",
        citations=[CitationDraft(evidence_id=retrieved[0].evidence_id)],
    )

    validated = GroundingValidator().validate(
        answer,
        deps.retrieved_passages,
        evidence_candidates=deps.evidence_candidates,
    )

    assert retrieved[0].chunk_id == chunk().chunk_id
    assert validated.citations[0].citation_label == "AAPL 10-K 2025"


def test_read_surrounding_chunks_registers_neighbors_as_trusted_evidence():
    deps = agent_deps(FakeRetriever())
    neighbor = chunk().model_copy(
        update={"chunk_id": UUID("00000000-0000-0000-0000-000000000002"), "text": "Neighbor evidence."}
    )

    async def surrounding(chunk_id, *, window=1):
        return {"previous_chunks": [neighbor], "next_chunks": []}

    deps.retriever.read_surrounding_chunks = surrounding
    deps.evidence_query = "Neighbor evidence"
    result = asyncio.run(
        read_surrounding_chunks(SimpleNamespace(deps=deps), chunk().chunk_id, window=1)
    )
    answer = AgentAnswer(
        answer="Neighbor evidence.",
        citations=[
            CitationDraft(
                evidence_id=next(
                    candidate.evidence_id
                    for candidate in result
                    if candidate.chunk_id == neighbor.chunk_id
                )
            )
        ],
    )

    validated = GroundingValidator().validate(
        answer,
        deps.retrieved_passages,
        evidence_candidates=deps.evidence_candidates,
    )

    assert any(candidate.chunk_id == neighbor.chunk_id for candidate in result)
    assert validated.citations[0].chunk_id == neighbor.chunk_id


def agent_deps(retriever: FakeRetriever) -> DocumentAgentDeps:
    return DocumentAgentDeps(
        user_id=uuid4(),
        thread_id=uuid4(),
        retriever=retriever,
        grounding_validator=GroundingValidator(),
        retrieval_filters=RetrievalFilters(tickers=("AAPL",)),
    )


def candidate(value: ChunkReference) -> EvidenceCandidate:
    return EvidenceCandidate(
        chunk_id=value.chunk_id,
        exact_quote=value.text,
        citation_label=value.citation_label,
        location_label=value.location_label,
    )
