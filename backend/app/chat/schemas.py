from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ChatThreadResponse(BaseModel):
    id: UUID
    title: str | None
    created_at: datetime
    updated_at: datetime


class ChatMessageResponse(BaseModel):
    id: UUID
    thread_id: UUID
    position: int
    role: Literal["user", "assistant"]
    content: str
    message_data: dict[str, object] = Field(default_factory=dict)
    created_at: datetime


class CreateThreadRequest(BaseModel):
    title: str | None = Field(default=None, max_length=255)


class UpdateThreadRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)


class UIMessagePart(BaseModel):
    type: str
    text: str | None = None


class UIMessage(BaseModel):
    id: str | None = None
    role: str
    content: str | None = None
    parts: list[UIMessagePart] = Field(default_factory=list)


class StreamChatRequest(BaseModel):
    thread_id: UUID = Field(alias="threadId")
    messages: list[UIMessage] = Field(default_factory=list)


class CitationSourceResponse(BaseModel):
    chunk_id: UUID
    chunk_index: int
    citation_index: int
    quoted_text: str
    chunk_text: str
    company_name: str
    filing_type: str
    filing_date: date
    page_number: int | None
    section: str | None
    source_url: str
    citation_label: str
    location_label: str
    previous_chunks: list["CitationChunkResponse"] = Field(default_factory=list)
    next_chunks: list["CitationChunkResponse"] = Field(default_factory=list)


class CitationChunkResponse(BaseModel):
    chunk_id: UUID
    chunk_index: int
    text: str
    page_number: int | None
    section: str | None
