import json
from types import SimpleNamespace

from app.assistant.outputs import AgentAnswer, GroundedAnswer
from app.config import settings
from smoke_assistance import SMOKE_CASES, format_answer, run_query


def test_default_smoke_query_targets_latest_apple_10k():
    filters = SMOKE_CASES[0].filters

    assert filters.tickers == ("AAPL",)
    assert filters.filing_types == ("10-K",)
    assert filters.fiscal_years == (2021, 2022, 2023, 2024, 2025)


def test_smoke_catalog_contains_all_ten_client_brief_questions():
    assert [case.key for case in SMOKE_CASES] == [
        "apple_revenue_mix",
        "amazon_segment_profitability",
        "nvidia_data_center",
        "microsoft_cloud_capacity",
        "alphabet_revenue_trends",
        "cross_company_risks",
        "supplier_concentration",
        "ai_cloud_investment",
        "geographic_exposure",
        "generative_ai_margins",
    ]
    assert len({case.question for case in SMOKE_CASES}) == 10
    assert SMOKE_CASES[-1].requires_refusal is True


def test_format_answer_excludes_full_retrieved_passages():
    rendered = json.loads(format_answer(GroundedAnswer(answer="No evidence.")))

    assert rendered == {"answer": "No evidence.", "citations": []}


def test_run_query_records_grounded_result_and_latency_without_model_override():
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

    result = asyncio.run(
        run_query(
            SMOKE_CASES[0],
            agent_runner=fake_agent,
            retriever=object(),
        )
    )

    assert "model" not in fake_agent.kwargs
    assert result.key == "apple_revenue_mix"
    assert result.question == SMOKE_CASES[0].question
    assert result.requires_refusal is False
    assert result.model == settings.OPENAI_CHAT_MODEL
    assert result.answer == "Insufficient evidence in the available filings."
    assert result.citation_count == 0
    assert result.elapsed_seconds >= 0
