import asyncio
from datetime import date
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.assistant.outputs import AgentAnswer, Citation, CitationDraft, GroundedAnswer
from app.chat.orchestrator import run_chat_turn
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
    def __init__(self):
        self.retrieve_calls = 0

    async def retrieve(self, query: str, **kwargs):
        self.retrieve_calls += 1
        return [passage()]


class FakeStore:
    def __init__(self):
        self.messages = []
        self.citations = []
        self.grounded_calls = []

    async def append_message(self, thread_id, role, content, message_data):
        message = {"id": str(uuid4()), "role": role, "content": content, "message_data": message_data}
        self.messages.append(message)
        return message

    async def append_grounded_answer(self, thread_id, content, message_data, citations):
        self.grounded_calls.append((thread_id, content, message_data, citations))
        message = {
            "id": str(uuid4()),
            "role": "assistant",
            "content": content,
            "message_data": message_data,
        }
        self.messages.append(message)
        self.citations.extend(citations)
        return message


def grounded_answer() -> GroundedAnswer:
    chunk = passage().center.chunk
    return GroundedAnswer(
        answer="Services revenue increased.",
        citations=[
            Citation(
                chunk_id=chunk.chunk_id,
                citation_index=0,
                quoted_text="Services revenue increased 14% in fiscal 2025.",
                citation_label=chunk.citation_label,
                location_label=chunk.location_label,
            )
        ],
    )


class FakeAgent:
    def __init__(self, answer):
        self.answer = answer
        self.usage_limits = None

    async def run(self, prompt, *, deps, usage_limits):
        self.usage_limits = usage_limits
        deps.add_passages(await deps.retriever.retrieve(prompt))
        return SimpleNamespace(output=self.answer)


class EvidenceAgent:
    async def run(self, prompt, *, deps, usage_limits):
        passages = await deps.retriever.retrieve(prompt)
        deps.add_passages(passages)
        evidence = deps.register_passage_evidence(passages, prompt)[0]
        return SimpleNamespace(
            output=AgentAnswer(
                answer="Services revenue increased.",
                citations=[CitationDraft(evidence_id=evidence.evidence_id)],
            )
        )


def test_run_chat_turn_persists_only_validated_answer_and_citations():
    store = FakeStore()
    retriever = FakeRetriever()
    agent = FakeAgent(grounded_answer())

    result = asyncio.run(
        run_chat_turn(
            user_id=uuid4(),
            thread_id=uuid4(),
            user_text="What happened to Services revenue?",
            store=store,
            agent_runner=agent,
            retriever=retriever,
            grounding_validator=GroundingValidator(),
        )
    )

    assert result.answer == "Services revenue increased."
    assert [message["role"] for message in store.messages] == ["user", "assistant"]
    assert len(store.citations) == 1
    assert len(store.grounded_calls) == 1
    assert store.citations[0]["citation_index"] == 0
    assert retriever.retrieve_calls == 1
    assert agent.usage_limits.request_limit == 4
    assert agent.usage_limits.tool_calls_limit == 6


def test_run_chat_turn_does_not_persist_assistant_on_grounding_failure():
    store = FakeStore()
    invalid = AgentAnswer(answer="Unsupported.", citations=[])

    with pytest.raises(GroundingError):
        asyncio.run(
            run_chat_turn(
                user_id=uuid4(),
                thread_id=uuid4(),
                user_text="What happened?",
                store=store,
                agent_runner=FakeAgent(invalid),
                retriever=FakeRetriever(),
                grounding_validator=GroundingValidator(),
            )
        )

    assert [message["role"] for message in store.messages] == ["user"]
    assert store.citations == []


def test_run_chat_turn_validates_registered_evidence_before_persistence():
    store = FakeStore()

    result = asyncio.run(
        run_chat_turn(
            user_id=uuid4(),
            thread_id=uuid4(),
            user_text="What happened to Services revenue?",
            store=store,
            agent_runner=EvidenceAgent(),
            retriever=FakeRetriever(),
            grounding_validator=GroundingValidator(),
        )
    )

    assert result.citations[0].quoted_text == passage().center.chunk.text
    assert len(store.citations) == 1
