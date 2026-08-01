from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class RetrievalFilters(BaseModel):
    tickers: tuple[str, ...] = ()
    filing_types: tuple[str, ...] = ()
    fiscal_years: tuple[int, ...] = ()

    @field_validator("tickers", "filing_types", mode="before")
    @classmethod
    def normalize_strings(cls, value: object) -> tuple[str, ...]:
        if value is None:
            return ()
        return tuple(str(item).strip().upper() for item in value if str(item).strip())


class ChunkReference(BaseModel):
    chunk_id: UUID
    document_id: UUID
    chunk_index: int
    text: str
    page_number: int | None
    section: str | None
    ticker: str
    company_name: str
    filing_type: str
    filing_date: date
    fiscal_year: int
    accession_number: str
    source_url: str

    @property
    def citation_label(self) -> str:
        return f"{self.ticker} {self.filing_type} {self.fiscal_year}"

    @property
    def location_label(self) -> str:
        parts = []
        if self.page_number is not None:
            parts.append(f"page {self.page_number}")
        if self.section:
            parts.append(self.section)
        return ", ".join(parts) or "unknown location"


class RankedChunk(BaseModel):
    chunk: ChunkReference
    rank: int = Field(ge=1)
    score: float
    source: Literal["semantic", "full_text"]


class FusedChunk(BaseModel):
    chunk: ChunkReference
    rrf_score: float
    semantic_rank: int | None = None
    full_text_rank: int | None = None
    semantic_score: float | None = None
    full_text_score: float | None = None


class SourcePassage(BaseModel):
    center: FusedChunk
    previous_chunks: list[ChunkReference] = Field(default_factory=list)
    next_chunks: list[ChunkReference] = Field(default_factory=list)
