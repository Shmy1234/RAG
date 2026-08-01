from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.auth.dependencies import AuthenticatedUser, get_current_user
from app.chat.schemas import (
    ChatMessageResponse,
    ChatThreadResponse,
    CreateThreadRequest,
    StreamChatRequest,
    UIMessage,
)
from app.chat.stub_stream import build_stub_reply, stream_stub_reply
from app.database.chats import ChatStore, ForbiddenThreadError, ThreadNotFoundError
from app.database.supabase import create_service_role_client

router = APIRouter(prefix="/chat", tags=["chat"])


def get_chat_store() -> ChatStore:
    return ChatStore(create_service_role_client())


CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]
ChatStoreDependency = Annotated[ChatStore, Depends(get_chat_store)]


def map_thread_error(error: Exception) -> HTTPException:
    if isinstance(error, ThreadNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")
    if isinstance(error, ForbiddenThreadError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Thread access denied")
    raise error


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


def latest_user_text(messages: list[UIMessage]) -> str:
    for message in reversed(messages):
        if message.role != "user":
            continue
        if message.content:
            return message.content
        part_text = "".join(part.text or "" for part in message.parts if part.type == "text")
        if part_text:
            return part_text
    return ""


@router.post("/stream")
async def stream_chat(
    request: StreamChatRequest,
    user: CurrentUser,
    store: ChatStoreDependency,
) -> StreamingResponse:
    try:
        await store.get_thread(user.id, request.thread_id)
    except (ThreadNotFoundError, ForbiddenThreadError) as error:
        raise map_thread_error(error) from error

    user_text = latest_user_text(request.messages)
    assistant_text = build_stub_reply(user_text)
    await store.append_message(request.thread_id, "user", user_text, {"phase": 3})

    async def response_stream() -> AsyncIterator[str]:
        async for chunk in stream_stub_reply(user_text):
            yield chunk
        await store.append_message(
            request.thread_id,
            "assistant",
            assistant_text,
            {"phase": 3, "stub": True},
        )

    return StreamingResponse(response_stream(), media_type="text/plain; charset=utf-8")
