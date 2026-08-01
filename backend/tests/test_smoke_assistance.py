import json

from app.assistant.outputs import GroundedAnswer
from smoke_assistance import QUERY_FILTERS, format_answer


def test_default_smoke_query_targets_latest_apple_10k():
    filters = QUERY_FILTERS["apple_revenue_mix"]

    assert filters.tickers == ("AAPL",)
    assert filters.filing_types == ("10-K",)
    assert filters.fiscal_years == (2025,)


def test_format_answer_excludes_full_retrieved_passages():
    rendered = json.loads(format_answer(GroundedAnswer(answer="No evidence.")))

    assert rendered == {"answer": "No evidence.", "citations": []}
