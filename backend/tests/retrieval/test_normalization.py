from app.retrieval.normalization import normalize_full_text_query


def test_removes_conversational_fillers():
    assert normalize_full_text_query("Can you actually show our revenue growth?") == "revenue growth ?"


def test_preserves_meaningful_finance_tokens_and_negation():
    query = "Could you compare not increasing margins in FY2024 versus FY2023 for AAPL?"
    assert normalize_full_text_query(query) == "compare not increasing margins FY2024 versus FY2023 AAPL ?"


def test_falls_back_to_original_when_every_word_is_filtered():
    assert normalize_full_text_query("I you we") == "I you we"
