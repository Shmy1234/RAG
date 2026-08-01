import asyncio
from datetime import date
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.assistant.outputs import AgentAnswer, Citation, CitationDraft, GroundedAnswer
from app.chat.orchestrator import run_chat_turn
from app.chat.routing import RouteDecision
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


def grounded_answer() -> GroundedAnswer:
    chunk = passage().center.chunk
    return GroundedAnswer(
        answer="Services revenue increased 14% in fiscal 2025.",
        citations=[
            Citation(
                chunk_id=chunk.chunk_id,
                citation_index=0,
                quoted_text=chunk.text,
                citation_label=chunk.citation_label,
                location_label=chunk.location_label,
            )
        ],
    )


class FakeStore:
    def __init__(self):
        self.messages = []
        self.grounded_calls = []

    async def append_message(self, thread_id, role, content, message_data):
        message = {"role": role, "content": content, "message_data": message_data}
        self.messages.append(message)
        return message

    async def append_grounded_answer(self, thread_id, content, message_data, citations):
        self.grounded_calls.append((thread_id, content, message_data, citations))
        message = {"role": "assistant", "content": content, "message_data": message_data}
        self.messages.append(message)
        return message


class FakeRouter:
    def __init__(self, decision: RouteDecision):
        self.decision = decision
        self.calls = []

    async def route(self, prompt: str):
        self.calls.append(prompt)
        return self.decision


class FakeRetriever:
    def __init__(self):
        self.retrieve_calls = 0

    async def retrieve(self, query: str, **kwargs):
        self.retrieve_calls += 1
        return [passage()]


class FakeQuickRagRunner:
    def __init__(self, answer: GroundedAnswer | None = None):
        self.answer = answer or grounded_answer()
        self.calls = []

    async def run(self, prompt, *, retriever, grounding_validator, on_stage):
        self.calls.append(prompt)
        await on_stage("searching")
        await on_stage("analyzing")
        await on_stage("validating")
        return self.answer


class EvidenceAgent:
    def __init__(self, answer: AgentAnswer | None = None):
        self.answer = answer
        self.calls = 0

    async def run(self, prompt, *, deps, usage_limits):
        self.calls += 1
        passages = await deps.retriever.retrieve(prompt)
        deps.add_passages(passages)
        await deps.on_stage("analyzing")
        if self.answer is not None:
            output = self.answer
        else:
            evidence = deps.register_passage_evidence(passages, prompt)[0]
            output = AgentAnswer(
                answer="Services revenue increased 14% in fiscal 2025.",
                citations=[CitationDraft(evidence_id=evidence.evidence_id)],
            )
        return SimpleNamespace(output=output)


def clock():
    values = iter([1.0, 1.01, 2.0, 2.02])
    return lambda: next(values)


def run_turn(route: RouteDecision, **overrides):
    store = overrides.pop("store", FakeStore())
    retriever = overrides.pop("retriever", FakeRetriever())
    agent = overrides.pop("agent_runner", EvidenceAgent())
    quick = overrides.pop("quick_rag_runner", FakeQuickRagRunner())
    stages = []

    async def report(stage):
        stages.append(stage)

    result = asyncio.run(
        run_chat_turn(
            user_id=uuid4(),
            thread_id=uuid4(),
            user_text="What happened to Services revenue?",
            store=store,
            router=FakeRouter(route),
            quick_rag_runner=quick,
            agent_runner=agent,
            retriever=retriever,
            grounding_validator=GroundingValidator(),
            on_stage=report,
            clock=clock(),
            **overrides,
        )
    )
    return result, store, retriever, agent, quick, stages


@pytest.mark.parametrize(
    ("route", "answer"),
    [
        ("instant", "Hi! How can I help with your filing research?"),
        ("direct", "I can explain how to use this filing workspace."),
    ],
)
def test_non_rag_routes_skip_retrieval_and_models(route, answer):
    result, store, retriever, agent, quick, stages = run_turn(
        RouteDecision(route=route, answer=answer)
    )

    assert result.answer == answer
    assert retriever.retrieve_calls == 0
    assert agent.calls == 0
    assert quick.calls == []
    assert stages == ["routing", "saving"]
    assert [message["role"] for message in store.messages] == ["user", "assistant"]


def test_quick_rag_delegates_to_one_pass_runner():
    result, store, retriever, agent, quick, stages = run_turn(
        RouteDecision(route="quick_rag")
    )

    assert result.citations
    assert quick.calls == ["What happened to Services revenue?"]
    assert agent.calls == 0
    assert retriever.retrieve_calls == 0
    assert stages == ["routing", "searching", "analyzing", "validating", "saving"]
    assert store.grounded_calls[0][3][0]["citation_index"] == 0


def test_deep_rag_runs_agent_and_validates_registered_evidence():
    result, store, retriever, agent, quick, stages = run_turn(RouteDecision(route="deep_rag"))

    assert result.citations[0].quoted_text == passage().center.chunk.text
    assert agent.calls == 1
    assert quick.calls == []
    assert retriever.retrieve_calls == 1
    assert stages == ["routing", "searching", "analyzing", "validating", "saving"]
    assert len(store.grounded_calls[0][3]) == 1


@pytest.mark.parametrize("route", ["instant", "direct", "quick_rag", "deep_rag"])
def test_all_routes_persist_route_and_non_negative_timing(route):
    decision = (
        RouteDecision(route=route, answer="Hello.")
        if route in {"instant", "direct"}
        else RouteDecision(route=route)
    )

    _, store, *_ = run_turn(decision)

    message_data = store.grounded_calls[0][2]
    assert message_data["route"] == route
    assert message_data["routing_ms"] == 10
    assert message_data["execution_ms"] == 20
    assert message_data["citations"] == store.grounded_calls[0][3]


def test_deep_rag_does_not_persist_assistant_on_grounding_failure():
    store = FakeStore()
    invalid = AgentAnswer(answer="Unsupported.", citations=[])

    with pytest.raises(GroundingError):
        run_turn(
            RouteDecision(route="deep_rag"),
            store=store,
            agent_runner=EvidenceAgent(invalid),
        )

    assert [message["role"] for message in store.messages] == ["user"]
    assert store.grounded_calls == []


def test_successful_turn_logs_route_and_timings_without_prompt(monkeypatch):
    logged = []

    class FakeLogger:
        def info(self, event, **context):
            logged.append((event, context))

    monkeypatch.setattr("app.chat.orchestrator.logger", FakeLogger())

    run_turn(RouteDecision(route="direct", answer="Hello."))

    assert logged == [
        (
            "chat_turn_completed",
            {"route": "direct", "routing_ms": 10, "execution_ms": 20},
        )
    ]


def test_instant_route_publishes_answer_before_assistant_persistence():
    order = []

    class OrderedStore(FakeStore):
        async def append_grounded_answer(self, thread_id, content, message_data, citations):
            order.append("saving")
            return await super().append_grounded_answer(
                thread_id, content, message_data, citations
            )

    async def publish(answer):
        order.append(("answer", answer.answer))

    asyncio.run(
        run_chat_turn(
            user_id=uuid4(),
            thread_id=uuid4(),
            user_text="Hi",
            store=OrderedStore(),
            router=FakeRouter(RouteDecision(route="instant", answer="Hello.")),
            quick_rag_runner=FakeQuickRagRunner(),
            agent_runner=EvidenceAgent(),
            retriever=FakeRetriever(),
            grounding_validator=GroundingValidator(),
            on_answer_ready=publish,
            clock=clock(),
        )
    )

    assert order == [("answer", "Hello."), "saving"]
