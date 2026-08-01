from datetime import date
from uuid import UUID, uuid4

from app.grounding.evidence import build_evidence_candidates
from app.retrieval.schemas import ChunkReference, FusedChunk, SourcePassage


def passage(text: str) -> SourcePassage:
    chunk = ChunkReference(
        chunk_id=UUID("00000000-0000-0000-0000-000000000001"),
        document_id=uuid4(),
        chunk_index=1,
        text=text,
        page_number=35,
        section="Net Sales",
        ticker="AAPL",
        company_name="Apple Inc.",
        filing_type="10-K",
        filing_date=date(2025, 10, 31),
        fiscal_year=2025,
        accession_number="0000320193-25-000079",
        source_url="https://www.sec.gov/example",
    )
    return SourcePassage(center=FusedChunk(chunk=chunk, rrf_score=1.0))


def test_builds_exact_bounded_candidate_around_services_table_values():
    text = (
        "Fiscal years 2025 2024 2023. " * 30
        + "Other product rows. " * 30
        + "Services (1), = 109,158. Services (1), = 96,169. Services (1), = 85,200. "
        + "Other balance sheet rows. " * 30
    )

    candidates = build_evidence_candidates([passage(text)], "What happened to Services revenue?")

    assert len(candidates) == 1
    assert candidates[0].exact_quote in text
    assert len(candidates[0].exact_quote) <= 600
    assert "Services (1), = 109,158" in candidates[0].exact_quote
    assert "85,200" in candidates[0].exact_quote
    assert candidates[0].citation_label == "AAPL 10-K 2025"
    assert candidates[0].location_label == "page 35, Net Sales"


def test_does_not_create_candidate_from_irrelevant_expense_chunk():
    text = "Research and development expense was 29,915 in fiscal 2025."

    candidates = build_evidence_candidates([passage(text)], "What happened to Services revenue?")

    assert candidates == []


def test_does_not_create_candidate_from_generic_revenue_chunk_without_services():
    text = "Total net revenue was 416,161 in fiscal 2025."

    candidates = build_evidence_candidates([passage(text)], "What happened to Services revenue?")

    assert candidates == []


def test_does_not_create_candidate_from_year_only_table_header():
    text = "Years ended September 27, 2025, September 28, 2024, and September 30, 2023."

    candidates = build_evidence_candidates([passage(text)], "What happened to Services revenue?")

    assert candidates == []
