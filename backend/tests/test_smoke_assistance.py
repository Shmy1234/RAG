import json
from types import SimpleNamespace

from app.assistant.outputs import AgentAnswer, GroundedAnswer
from app.config import settings
from smoke_assistance import QUERY_FILTERS, format_answer, run_query


def test_default_smoke_query_targets_latest_apple_10k():
    filters = QUERY_FILTERS["apple_revenue_mix"]

    assert filters.tickers == ("AAPL",)
    assert filters.filing_types == ("10-K",)
    assert filters.fiscal_years == (2025,)


def test_format_answer_excludes_full_retrieved_passages():
    rendered = json.loads(format_answer(GroundedAnswer(answer="No evidence.")))

    assert rendered == {"answer": "No evidence.", "citations": []}


def test_run_query_uses_configured_agent_without_model_override(capsys):
    class FakeAgent:
        def __init__(self):
            self.kwargs = None

        async def run(self, prompt, **kwargs):
            self.kwargs = kwargs
            return SimpleNamespace(
                output=AgentAnswer(answer="Insufficient evidence in the available filings.")
            )

    fake_agent = FakeAgent()

    import asyncio

    asyncio.run(
        run_query(
            agent_runner=fake_agent,
            retriever=object(),
        )
    )

    assert "model" not in fake_agent.kwargs
    assert f"model={settings.OPENAI_CHAT_MODEL}" in capsys.readouterr().out
