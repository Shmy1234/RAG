import asyncio
import json
from datetime import date
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.assistant.outputs import AgentAnswer, CitationDraft
from app.chat.quick_rag import INSUFFICIENT_EVIDENCE_ANSWER, QuickRagRunner
from app.chat.stages import RetrievalError
from app.grounding.validator import GroundingError, GroundingValidator
from app.retrieval.schemas import ChunkReference, FusedChunk, SourcePassage


def passage() -> SourcePassage:
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


class FakeRetriever:
    def __init__(self, passages):
        self.passages = passages
        self.calls = []

    async def retrieve(self, query: str, **kwargs):
        self.calls.append((query, kwargs))
        return self.passages


class EvidenceAnswerRunner:
    def __init__(self, answer: str = "Services revenue increased 14% in fiscal 2025."):
        self.answer = answer
        self.calls = []

    async def run(self, prompt: str, *, usage_limits):
        payload = json.loads(prompt)
        self.calls.append((payload, usage_limits))
        evidence_id = payload["evidence"][0]["evidence_id"]
        return SimpleNamespace(
            output=AgentAnswer(
                answer=self.answer,
                citations=[CitationDraft(evidence_id=evidence_id)],
            )
        )


def test_quick_rag_retrieves_once_and_returns_validated_citation():
    retriever = FakeRetriever([passage()])
    model = EvidenceAnswerRunner()
    stages = []

    async def report(stage):
        stages.append(stage)

    result = asyncio.run(
        QuickRagRunner(model).run(
            "What happened to Services revenue?",
            retriever=retriever,
            grounding_validator=GroundingValidator(),
            on_stage=report,
        )
    )

    assert retriever.calls == [
        (
            "What happened to Services revenue?",
            {"top_k": 5, "candidate_k": 50},
        )
    ]
    assert len(model.calls) == 1
    assert model.calls[0][0]["question"] == "What happened to Services revenue?"
    assert model.calls[0][0]["evidence"][0]["exact_quote"] == passage().center.chunk.text
    assert model.calls[0][1].request_limit == 1
    assert result.citations[0].chunk_id == passage().center.chunk.chunk_id
    assert stages == ["searching", "analyzing", "validating"]


def test_quick_rag_empty_result_skips_answer_model():
    retriever = FakeRetriever([])
    model = EvidenceAnswerRunner()

    result = asyncio.run(
        QuickRagRunner(model).run(
            "What happened?",
            retriever=retriever,
            grounding_validator=GroundingValidator(),
        )
    )

    assert result.answer == INSUFFICIENT_EVIDENCE_ANSWER
    assert result.citations == []
    assert model.calls == []


def test_quick_rag_rejects_unsupported_model_answer():
    class UnsupportedRunner:
        async def run(self, prompt: str, *, usage_limits):
            return SimpleNamespace(output=AgentAnswer(answer="Unsupported claim.", citations=[]))

    with pytest.raises(GroundingError):
        asyncio.run(
            QuickRagRunner(UnsupportedRunner()).run(
                "What happened to Services revenue?",
                retriever=FakeRetriever([passage()]),
                grounding_validator=GroundingValidator(),
            )
        )


def test_quick_rag_maps_retrieval_boundary_failure():
    class BrokenRetriever:
        async def retrieve(self, query: str, **kwargs):
            raise RuntimeError("embedding service unavailable")

    with pytest.raises(RetrievalError):
        asyncio.run(
            QuickRagRunner(EvidenceAnswerRunner()).run(
                "What happened to Services revenue?",
                retriever=BrokenRetriever(),
                grounding_validator=GroundingValidator(),
            )
        )
