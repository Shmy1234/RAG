from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.assistant.agent import document_agent
from app.assistant.deps import StageCallback
from app.auth.dependencies import AuthenticatedUser, get_current_user
from app.chat.orchestrator import run_chat_turn
from app.chat.schemas import (
    ChatMessageResponse,
    ChatThreadResponse,
    CitationSourceResponse,
    CreateThreadRequest,
    StreamChatRequest,
    UIMessage,
    UpdateThreadRequest,
)
from app.chat.streaming import stream_chat_turn
from app.database.chats import ChatStore, ForbiddenThreadError, ThreadNotFoundError
from app.database.supabase import create_service_role_client
from app.grounding.validator import GroundingValidator
from app.retrieval.retriever import DocumentRetriever
from ingest.repository import create_sessionmaker

router = APIRouter(prefix="/chat", tags=["chat"])


def get_chat_store() -> ChatStore:
    return ChatStore(create_service_role_client())


def get_document_retriever() -> DocumentRetriever:
    return DocumentRetriever(session_factory=create_sessionmaker())


def get_agent_runner():
    return document_agent


def get_grounding_validator() -> GroundingValidator:
    return GroundingValidator()


CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]
ChatStoreDependency = Annotated[ChatStore, Depends(get_chat_store)]
RetrieverDependency = Annotated[DocumentRetriever, Depends(get_document_retriever)]
AgentDependency = Annotated[object, Depends(get_agent_runner)]
GroundingDependency = Annotated[GroundingValidator, Depends(get_grounding_validator)]


def map_thread_error(error: Exception) -> HTTPException:
    if isinstance(error, ThreadNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")
    if isinstance(error, ForbiddenThreadError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Thread access denied")
    raise error


def _citation_chunk_response(chunk: dict[str, object]) -> dict[str, object]:
    return {
        "chunk_id": chunk["id"],
        "chunk_index": chunk["chunk_index"],
        "text": chunk["text"],
        "page_number": chunk.get("page_number"),
        "section": chunk.get("section"),
    }


@router.get("/threads", response_model=list[ChatThreadResponse])
async def list_threads(
    user: CurrentUser,
    store: ChatStoreDependency,
) -> list[dict[str, object]]:
    return await store.list_threads(user.id)


@router.post("/threads", response_model=ChatThreadResponse)
async def create_thread(
    request: CreateThreadRequest,
    user: CurrentUser,
    store: ChatStoreDependency,
) -> dict[str, object]:
    if user.email is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authenticated user email is required",
        )
    await store.ensure_user(user.id, user.email)
    return await store.create_thread(user.id, request.title)


@router.patch("/threads/{thread_id}", response_model=ChatThreadResponse)
async def update_thread(
    thread_id: UUID,
    request: UpdateThreadRequest,
    user: CurrentUser,
    store: ChatStoreDependency,
) -> dict[str, object]:
    try:
        return await store.update_thread_title(user.id, thread_id, request.title)
    except (ThreadNotFoundError, ForbiddenThreadError) as error:
        raise map_thread_error(error) from error


@router.get("/threads/{thread_id}/messages", response_model=list[ChatMessageResponse])
async def list_messages(
    thread_id: UUID,
    user: CurrentUser,
    store: ChatStoreDependency,
) -> list[dict[str, object]]:
    try:
        return await store.list_messages(user.id, thread_id)
    except (ThreadNotFoundError, ForbiddenThreadError) as error:
        raise map_thread_error(error) from error


@router.get(
    "/messages/{message_id}/citations/{citation_index}/source",
    response_model=CitationSourceResponse,
)
async def get_citation_source(
    message_id: UUID,
    citation_index: int,
    user: CurrentUser,
    store: ChatStoreDependency,
) -> dict[str, object]:
    row = await store.get_citation_source(user.id, message_id, citation_index)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Citation not found")
    chunk = row["document_chunks"]
    document = chunk["source_documents"]
    page_number = chunk.get("page_number")
    section = chunk.get("section")
    location_parts = []
    if page_number is not None:
        location_parts.append(f"page {page_number}")
    if section:
        location_parts.append(section)
    return {
        "chunk_id": row["chunk_id"],
        "chunk_index": chunk["chunk_index"],
        "citation_index": row["citation_index"],
        "quoted_text": row["quoted_text"],
        "chunk_text": chunk["text"],
        "company_name": document["company_name"],
        "filing_type": document["filing_type"],
        "filing_date": document["filing_date"],
        "page_number": page_number,
        "section": section,
        "source_url": document["source_url"],
        "citation_label": f"{document['ticker']} {document['filing_type']}",
        "location_label": ", ".join(location_parts) or "unknown location",
        "previous_chunks": [
            _citation_chunk_response(item) for item in row["previous_chunks"]
        ],
        "next_chunks": [_citation_chunk_response(item) for item in row["next_chunks"]],
    }


def latest_user_text(messages: list[UIMessage]) -> str:
    for message in reversed(messages):
        if message.role != "user":
            continue
        if message.content and message.content.strip():
            return message.content
        part_text = "".join(part.text or "" for part in message.parts if part.type == "text")
        if part_text.strip():
            return part_text
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail="A non-blank user message is required",
    )


@router.post("/stream")
async def stream_chat(
    request: StreamChatRequest,
    user: CurrentUser,
    store: ChatStoreDependency,
    retriever: RetrieverDependency,
    agent_runner: AgentDependency,
    grounding_validator: GroundingDependency,
) -> StreamingResponse:
    try:
        await store.get_thread(user.id, request.thread_id)
    except (ThreadNotFoundError, ForbiddenThreadError) as error:
        raise map_thread_error(error) from error

    user_text = latest_user_text(request.messages)

    async def run_turn(on_stage: StageCallback):
        return await run_chat_turn(
            user_id=user.id,
            thread_id=request.thread_id,
            user_text=user_text,
            store=store,
            agent_runner=agent_runner,
            retriever=retriever,
            grounding_validator=grounding_validator,
            on_stage=on_stage,
        )

    # Auth and ownership already failed as HTTP above. Everything from here runs
    # inside the stream so the client sees real stage progress, and failures
    # arrive as typed data-error parts rather than a dead connection.
    return StreamingResponse(
        stream_chat_turn(run_turn),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
