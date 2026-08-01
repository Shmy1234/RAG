import asyncio
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.chat.routing import ROUTING_INSTRUCTIONS, ChatRouter, RouteDecision


class FakeRouteRunner:
    def __init__(self, decision: RouteDecision):
        self.decision = decision
        self.calls: list[str] = []
        self.usage_limits = None

    async def run(self, prompt: str, *, usage_limits):
        self.calls.append(prompt)
        self.usage_limits = usage_limits
        return SimpleNamespace(output=self.decision)


@pytest.mark.parametrize("prompt", ["hi", "  Hi!  ", "HELLO.", "thanks", "Thank you!"])
def test_instant_prompt_skips_model_runner(prompt: str):
    runner = FakeRouteRunner(RouteDecision(route="deep_rag"))

    decision = asyncio.run(ChatRouter(runner).route(prompt))

    assert decision.route == "instant"
    assert decision.answer
    assert runner.calls == []


def test_near_match_uses_one_typed_model_call():
    expected = RouteDecision(route="quick_rag")
    runner = FakeRouteRunner(expected)

    decision = asyncio.run(ChatRouter(runner).route("Hi, summarize Apple's filing"))

    assert decision == expected
    assert runner.calls == ["Hi, summarize Apple's filing"]
    assert runner.usage_limits.request_limit == 1


def test_direct_route_reuses_answer_from_routing_call():
    expected = RouteDecision(
        route="direct",
        answer="I can help you research SEC filings and inspect supporting citations.",
    )
    runner = FakeRouteRunner(expected)

    decision = asyncio.run(ChatRouter(runner).route("What can you help me do?"))

    assert decision == expected
    assert len(runner.calls) == 1


@pytest.mark.parametrize(
    "data",
    [
        {"route": "instant"},
        {"route": "direct", "answer": "   "},
        {"route": "quick_rag", "answer": "Untrusted answer"},
        {"route": "deep_rag", "answer": "Untrusted answer"},
    ],
)
def test_route_decision_rejects_route_inappropriate_answers(data):
    with pytest.raises(ValidationError):
        RouteDecision.model_validate(data)


def test_routing_contract_keeps_external_facts_out_of_direct_lane():
    assert "company" in ROUTING_INSTRUCTIONS
    assert "filing" in ROUTING_INSTRUCTIONS
    assert "financial" in ROUTING_INSTRUCTIONS
    assert "citation" in ROUTING_INSTRUCTIONS
    assert "Ambiguous" in ROUTING_INSTRUCTIONS
