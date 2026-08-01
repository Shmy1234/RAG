import asyncio
from datetime import date
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.assistant.outputs import Citation, GroundedAnswer
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
    async def retrieve(self, query: str, **kwargs):
        return [passage()]


class FakeStore:
    def __init__(self):
        self.messages = []
        self.citations = []

    async def append_message(self, thread_id, role, content, message_data):
        message = {"id": str(uuid4()), "role": role, "content": content, "message_data": message_data}
        self.messages.append(message)
        return message

    async def append_citations(self, message_id, citations):
        self.citations.extend(citations)


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

    async def run(self, prompt, *, deps):
        return SimpleNamespace(output=self.answer)


def test_run_chat_turn_persists_only_validated_answer_and_citations():
    store = FakeStore()

    result = asyncio.run(
        run_chat_turn(
            user_id=uuid4(),
            thread_id=uuid4(),
            user_text="What happened to Services revenue?",
            store=store,
            agent_runner=FakeAgent(grounded_answer()),
            retriever=FakeRetriever(),
            grounding_validator=GroundingValidator(),
        )
    )

    assert result.answer == "Services revenue increased."
    assert [message["role"] for message in store.messages] == ["user", "assistant"]
    assert len(store.citations) == 1
    assert store.citations[0]["citation_index"] == 0


def test_run_chat_turn_does_not_persist_assistant_on_grounding_failure():
    store = FakeStore()
    invalid = grounded_answer().model_copy(update={"citations": []})

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
