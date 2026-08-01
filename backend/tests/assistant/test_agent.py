import asyncio
from datetime import date
from uuid import UUID, uuid4

from pydantic_ai.models.test import TestModel

from app.assistant.agent import document_agent
from app.assistant.deps import DocumentAgentDeps
from app.assistant.outputs import Citation, GroundedAnswer
from app.retrieval.schemas import ChunkReference, SourcePassage


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
    async def retrieve(self, query: str, *, top_k: int = 5, **kwargs):
        assert query
        assert top_k == 5
        return [SourcePassage(center={"chunk": chunk(), "rrf_score": 1.0})]

    async def read_chunk(self, chunk_id):
        return chunk()

    async def read_surrounding_chunks(self, chunk_id, *, window=1):
        return {"previous_chunks": [], "next_chunks": []}


class FakeValidator:
    def validate(self, answer, passages):
        return answer


def test_document_agent_returns_typed_output_and_exposes_search_tool():
    expected = {
        "answer": "Services revenue increased.",
        "citations": [
            {
                "chunk_id": str(chunk().chunk_id),
                "citation_index": 0,
                "quoted_text": "Services revenue increased.",
                "citation_label": "AAPL 10-K 2025",
                "location_label": "page 42, Results",
            }
        ],
        "cited_passages": [],
    }
    deps = DocumentAgentDeps(
        user_id=uuid4(),
        thread_id=uuid4(),
        retriever=FakeRetriever(),
        grounding_validator=FakeValidator(),
    )

    result = asyncio.run(
        document_agent.run(
            "Find Services revenue",
            deps=deps,
            model=TestModel(
                call_tools=["search_filings"],
                custom_output_args=expected,
            ),
        )
    )

    assert isinstance(result.output, GroundedAnswer)
    assert result.output.citations[0].citation_index == 0
    assert isinstance(result.output.citations[0], Citation)
