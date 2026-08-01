from uuid import UUID

from pydantic import BaseModel, Field

from app.retrieval.schemas import SourcePassage


class Citation(BaseModel):
    chunk_id: UUID
    citation_index: int = Field(ge=0)
    quoted_text: str = Field(min_length=1)
    citation_label: str
    location_label: str


class CitationDraft(BaseModel):
    evidence_id: UUID


class AgentAnswer(BaseModel):
    answer: str
    citations: list[CitationDraft] = Field(default_factory=list)


class GroundedAnswer(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    cited_passages: list[SourcePassage] = Field(default_factory=list)
