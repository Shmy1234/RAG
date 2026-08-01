# Phase 3 Chat Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an authenticated end-to-end chat shell where a user can create a thread, send a message, receive a streamed stub assistant response from FastAPI, and reload persisted history.

**Architecture:** The backend owns thread authorization, persistence, and streaming. The frontend owns route state, thread navigation, and a simple chat interface connected to FastAPI with the Supabase bearer token. The assistant response is deliberately stubbed so Phase 3 proves the full-stack contract before ingestion, retrieval, grounding, and citation metadata are introduced.

**Tech Stack:** FastAPI, Pydantic v2, Supabase Python client, Vite, React 19, React Router, TypeScript, Tailwind CSS, shadcn/ui button, `@ai-sdk/react`, `ai`

## Global Constraints

- Do not implement retrieval, OpenAI calls, PydanticAI orchestration, grounding, or citation rendering in Phase 3.
- Backend request handlers must be `async def`.
- Backend authentication must use `get_current_user`; unauthenticated requests fail before database work.
- Backend database access must go through focused helpers under `backend/app/database/`.
- Frontend HTTP JSON calls must use `src/lib/api.ts`; streaming transport may call `fetch` through the AI SDK transport only because `api.ts` is not a streaming client.
- Frontend env reads must stay isolated to `src/lib/env.ts`.
- Use TypeScript strict without `any`.
- Do not add frontend tests; verify with `pnpm tsc --noEmit`, `pnpm lint`, and `pnpm build`.
- Backend fast tests must not call Supabase, OpenAI, or the network.
- Preserve unrelated worktree changes.

---

## Chosen Approach

Use a backend-led vertical slice with a plain text stream for the stub assistant response.

Other viable approaches were rejected for Phase 3:

- Full AI SDK data-stream protocol now: better long-term fit for citations, but it forces backend stream protocol work before citation/source parts exist.
- Hand-rolled frontend streaming: avoids a frontend dependency, but the architecture already selected AI SDK UI primitives and Phase 6 will need the same client surface.

The chosen approach adds the AI SDK dependency now, isolates it to one chat component, and keeps the FastAPI stub stream easy to inspect and test.

---

## File Structure

Backend:

- Create `backend/app/api/chat.py`: FastAPI routes for thread CRUD, message history, and stub streaming.
- Create `backend/app/chat/schemas.py`: request and response Pydantic models shared by chat routes.
- Create `backend/app/chat/stub_stream.py`: deterministic assistant text chunks for Phase 3.
- Create `backend/app/database/chats.py`: Supabase table operations for threads and messages with user ownership checks.
- Modify `backend/app/main.py`: include the chat router.
- Create `backend/tests/database/test_chats.py`: unit tests for helper behavior with a fake Supabase query chain.
- Create `backend/tests/api/test_chat.py`: route tests that override auth and chat storage dependencies.

Frontend:

- Modify `frontend/package.json` and `frontend/pnpm-lock.yaml`: add `@ai-sdk/react` and `ai`.
- Modify `frontend/src/App.tsx`: replace the existing `/app` protected page with chat routes.
- Create `frontend/src/lib/chat-api.ts`: typed product calls for thread CRUD and message history.
- Create `frontend/src/lib/chat-stream.ts`: builds AI SDK transport headers from Supabase session.
- Create `frontend/src/pages/ChatPage.tsx`: protected route container for sidebar and selected thread.
- Create `frontend/src/components/chat/ThreadSidebar.tsx`: thread list and create-thread action.
- Create `frontend/src/components/chat/ChatThread.tsx`: message list, input form, streaming state, and reload behavior.
- Create `frontend/src/components/chat/message-format.ts`: UI message text extraction helpers.
- Modify `frontend/src/pages/ProtectedPage.tsx`: remove or leave unused after routing switches to `ChatPage`.

---

### Task 1: Backend Chat Schemas and Stub Stream

**Files:**
- Create: `backend/app/chat/schemas.py`
- Create: `backend/app/chat/stub_stream.py`

**Interfaces:**
- Produces: `ChatThreadResponse`, `ChatMessageResponse`, `CreateThreadRequest`, `StreamChatRequest`, `UIMessage`
- Produces: `stream_stub_reply(user_text: str) -> AsyncIterator[str]`

- [ ] **Step 1: Define chat response schemas**

Create `backend/app/chat/schemas.py`:

```python
from datetime import datetime
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
```

- [ ] **Step 2: Add deterministic stub streaming**

Create `backend/app/chat/stub_stream.py`:

```python
from collections.abc import AsyncIterator


def build_stub_reply(user_text: str) -> str:
    prompt = user_text.strip()
    if not prompt:
        return "I received your message. Phase 3 is wired for streaming, and retrieval will be added in Phase 5."
    return (
        "Stub response: I received your question about "
        f"\"{prompt[:120]}\". Retrieval and grounded citations will be added in Phase 5 and Phase 6."
    )


async def stream_stub_reply(user_text: str) -> AsyncIterator[str]:
    reply = build_stub_reply(user_text)
    for word in reply.split(" "):
        yield f"{word} "
```

- [ ] **Step 3: Run backend schema import check**

Run:

```bash
cd backend
uv run python -c "from app.chat.schemas import StreamChatRequest; from app.chat.stub_stream import build_stub_reply; print(StreamChatRequest, build_stub_reply('x'))"
```

Expected: command prints the imported class and a stub response.

---

### Task 2: Backend Chat Persistence Helper

**Files:**
- Create: `backend/app/database/chats.py`
- Test: `backend/tests/database/test_chats.py`

**Interfaces:**
- Consumes: `supabase.Client`
- Produces: `ChatStore`
- Produces: `ForbiddenThreadError`
- Produces: `ThreadNotFoundError`
- Produces methods:
  - `list_threads(user_id: UUID) -> list[dict[str, object]]`
  - `create_thread(user_id: UUID, title: str | None) -> dict[str, object]`
  - `get_thread(user_id: UUID, thread_id: UUID) -> dict[str, object]`
  - `list_messages(user_id: UUID, thread_id: UUID) -> list[dict[str, object]]`
  - `append_message(thread_id: UUID, role: str, content: str, message_data: dict[str, object]) -> dict[str, object]`

- [ ] **Step 1: Write failing tests for ownership errors**

Create `backend/tests/database/test_chats.py` with fake responses for these cases:

```python
from uuid import uuid4

import pytest

from app.database.chats import ChatStore, ForbiddenThreadError, ThreadNotFoundError


class FakeExecute:
    def __init__(self, data):
        self.data = data

    def execute(self):
        return self


def test_get_thread_raises_not_found_when_no_row():
    store = ChatStore(client=FakeClient({"chat_threads": []}))
    with pytest.raises(ThreadNotFoundError):
        store.get_thread(uuid4(), uuid4())


def test_get_thread_raises_forbidden_for_other_user():
    owner_id = uuid4()
    other_id = uuid4()
    thread_id = uuid4()
    store = ChatStore(
        client=FakeClient(
            {
                "chat_threads": [
                    {
                        "id": str(thread_id),
                        "user_id": str(other_id),
                        "title": "Other",
                        "created_at": "2026-08-01T12:00:00Z",
                        "updated_at": "2026-08-01T12:00:00Z",
                    }
                ]
            }
        )
    )
    with pytest.raises(ForbiddenThreadError):
        store.get_thread(owner_id, thread_id)
```

Include a `FakeClient` query chain in the same test file with `table`, `select`, `eq`, `order`, `limit`, `insert`, and `single` methods that return `self`, record filters, and return `FakeExecute(filtered_rows)`.

- [ ] **Step 2: Implement ownership-aware helper**

Create `backend/app/database/chats.py`:

```python
from uuid import UUID

from supabase import Client


class ThreadNotFoundError(Exception):
    pass


class ForbiddenThreadError(Exception):
    pass


class ChatStore:
    def __init__(self, client: Client):
        self.client = client

    def list_threads(self, user_id: UUID) -> list[dict[str, object]]:
        response = (
            self.client.table("chat_threads")
            .select("id,title,created_at,updated_at")
            .eq("user_id", str(user_id))
            .order("updated_at", desc=True)
            .execute()
        )
        return list(response.data or [])

    def create_thread(self, user_id: UUID, title: str | None) -> dict[str, object]:
        response = (
            self.client.table("chat_threads")
            .insert({"user_id": str(user_id), "title": title})
            .execute()
        )
        return dict(response.data[0])

    def get_thread(self, user_id: UUID, thread_id: UUID) -> dict[str, object]:
        response = (
            self.client.table("chat_threads")
            .select("id,user_id,title,created_at,updated_at")
            .eq("id", str(thread_id))
            .limit(1)
            .execute()
        )
        rows = response.data or []
        if not rows:
            raise ThreadNotFoundError()
        row = dict(rows[0])
        if row["user_id"] != str(user_id):
            raise ForbiddenThreadError()
        return row

    def list_messages(self, user_id: UUID, thread_id: UUID) -> list[dict[str, object]]:
        self.get_thread(user_id, thread_id)
        response = (
            self.client.table("chat_messages")
            .select("id,thread_id,position,role,content,message_data,created_at")
            .eq("thread_id", str(thread_id))
            .order("position")
            .execute()
        )
        return list(response.data or [])

    def append_message(
        self,
        thread_id: UUID,
        role: str,
        content: str,
        message_data: dict[str, object],
    ) -> dict[str, object]:
        existing = (
            self.client.table("chat_messages")
            .select("position")
            .eq("thread_id", str(thread_id))
            .order("position", desc=True)
            .limit(1)
            .execute()
        )
        next_position = 0
        if existing.data:
            next_position = int(existing.data[0]["position"]) + 1
        response = (
            self.client.table("chat_messages")
            .insert(
                {
                    "thread_id": str(thread_id),
                    "position": next_position,
                    "role": role,
                    "content": content,
                    "message_data": message_data,
                }
            )
            .execute()
        )
        return dict(response.data[0])
```

- [ ] **Step 3: Run helper tests**

Run:

```bash
cd backend
uv run pytest tests/database/test_chats.py -v
```

Expected: all tests pass without network access.

---

### Task 3: Backend Chat Routes

**Files:**
- Create: `backend/app/api/chat.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/api/test_chat.py`

**Interfaces:**
- Consumes: `AuthenticatedUser`, `get_current_user`, `create_service_role_client`, `ChatStore`
- Produces routes:
  - `GET /chat/threads`
  - `POST /chat/threads`
  - `GET /chat/threads/{thread_id}/messages`
  - `POST /chat/stream`

- [ ] **Step 1: Write route tests for status mapping**

Create `backend/tests/api/test_chat.py` with `httpx.AsyncClient` against the FastAPI app and dependency overrides:

```python
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient

from app.auth.dependencies import AuthenticatedUser, get_current_user
from app.api.chat import get_chat_store
from app.main import app


@pytest.fixture
def user() -> AuthenticatedUser:
    return AuthenticatedUser(id=uuid4(), email="analyst@equity-research-assistant.example")


class MemoryChatStore:
    def __init__(self):
        self.thread_id = uuid4()

    def list_threads(self, user_id):
        return []

    def create_thread(self, user_id, title):
        now = datetime.now(timezone.utc).isoformat()
        return {
            "id": str(self.thread_id),
            "title": title,
            "created_at": now,
            "updated_at": now,
        }

    def list_messages(self, user_id, thread_id):
        return []


@pytest.mark.anyio
async def test_threads_requires_auth():
    app.dependency_overrides.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/chat/threads")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.anyio
async def test_create_thread_returns_thread(user):
    async def override_user():
        return user

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_chat_store] = MemoryChatStore
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/chat/threads", json={"title": "Apple revenue mix"})
    app.dependency_overrides.clear()
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["title"] == "Apple revenue mix"
```

Use a route-level dependency for `ChatStore` in the implementation so the test can override it with an in-memory store after the first failure.

- [ ] **Step 2: Implement route dependency and CRUD endpoints**

Create `backend/app/api/chat.py`:

```python
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


def map_thread_error(error: Exception) -> HTTPException:
    if isinstance(error, ThreadNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")
    if isinstance(error, ForbiddenThreadError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Thread access denied")
    raise error


@router.get("/threads", response_model=list[ChatThreadResponse])
async def list_threads(
    user: AuthenticatedUser = Depends(get_current_user),
    store: ChatStore = Depends(get_chat_store),
) -> list[dict[str, object]]:
    return store.list_threads(user.id)


@router.post("/threads", response_model=ChatThreadResponse)
async def create_thread(
    request: CreateThreadRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    store: ChatStore = Depends(get_chat_store),
) -> dict[str, object]:
    return store.create_thread(user.id, request.title)


@router.get("/threads/{thread_id}/messages", response_model=list[ChatMessageResponse])
async def list_messages(
    thread_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    store: ChatStore = Depends(get_chat_store),
) -> list[dict[str, object]]:
    try:
        return store.list_messages(user.id, thread_id)
    except (ThreadNotFoundError, ForbiddenThreadError) as error:
        raise map_thread_error(error) from error
```

- [ ] **Step 3: Implement stream endpoint**

Add to `backend/app/api/chat.py`:

```python
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
    user: AuthenticatedUser = Depends(get_current_user),
    store: ChatStore = Depends(get_chat_store),
) -> StreamingResponse:
    try:
        store.get_thread(user.id, request.thread_id)
    except (ThreadNotFoundError, ForbiddenThreadError) as error:
        raise map_thread_error(error) from error

    user_text = latest_user_text(request.messages)
    assistant_text = build_stub_reply(user_text)
    store.append_message(request.thread_id, "user", user_text, {"phase": 3})
    store.append_message(request.thread_id, "assistant", assistant_text, {"phase": 3, "stub": True})
    return StreamingResponse(stream_stub_reply(user_text), media_type="text/plain; charset=utf-8")
```

- [ ] **Step 4: Register router**

Modify `backend/app/main.py`:

```python
from app.api.chat import router as chat_router

app.include_router(auth_router)
app.include_router(chat_router)
```

- [ ] **Step 5: Run route tests**

Run:

```bash
cd backend
uv run pytest tests/api/test_chat.py -v
```

Expected: route tests pass.

---

### Task 4: Frontend Chat API Types

**Files:**
- Create: `frontend/src/lib/chat-api.ts`

**Interfaces:**
- Consumes: `api`
- Produces: `ChatThread`, `ChatMessage`, `chatApi`

- [ ] **Step 1: Add typed endpoint client**

Create `frontend/src/lib/chat-api.ts`:

```ts
import { api } from '@/lib/api'

export type ChatThread = {
  id: string
  title: string | null
  created_at: string
  updated_at: string
}

export type ChatMessage = {
  id: string
  thread_id: string
  position: number
  role: 'user' | 'assistant'
  content: string
  message_data: Record<string, unknown>
  created_at: string
}

export const chatApi = {
  listThreads: () => api.get<ChatThread[]>('/chat/threads'),
  createThread: (title: string | null) => api.post<ChatThread>('/chat/threads', { title }),
  listMessages: (threadId: string) =>
    api.get<ChatMessage[]>(`/chat/threads/${encodeURIComponent(threadId)}/messages`),
}
```

- [ ] **Step 2: Type-check**

Run:

```bash
cd frontend
pnpm tsc --noEmit
```

Expected: exit code 0.

---

### Task 5: Frontend AI SDK Transport

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/pnpm-lock.yaml`
- Create: `frontend/src/lib/chat-stream.ts`

**Interfaces:**
- Consumes: `env.apiBaseUrl`, `supabase.auth.getSession()`
- Produces: `createChatTransport(): TextStreamChatTransport`

- [ ] **Step 1: Add AI SDK packages**

Run:

```bash
cd frontend
pnpm add @ai-sdk/react ai
```

Expected: `package.json` and `pnpm-lock.yaml` update with packages older than the configured 7-day minimum release age.

- [ ] **Step 2: Add stream transport factory**

Create `frontend/src/lib/chat-stream.ts`:

```ts
import { TextStreamChatTransport } from 'ai'

import { env } from '@/lib/env'
import { supabase } from '@/lib/supabase'

export function createChatTransport() {
  return new TextStreamChatTransport({
    api: new URL('/chat/stream', `${env.apiBaseUrl}/`).toString(),
    headers: async () => {
      const { data } = await supabase.auth.getSession()
      if (!data.session?.access_token) return {}
      return { Authorization: `Bearer ${data.session.access_token}` }
    },
  })
}
```

- [ ] **Step 3: Type-check**

Run:

```bash
cd frontend
pnpm tsc --noEmit
```

Expected: `TextStreamChatTransport` import and async `headers` option type-check with the installed AI SDK version. If the installed version requires a different header callback name, update only `frontend/src/lib/chat-stream.ts` and keep the exported `createChatTransport()` interface unchanged.

---

### Task 6: Frontend Chat Routes and Page Shell

**Files:**
- Modify: `frontend/src/App.tsx`
- Create: `frontend/src/pages/ChatPage.tsx`
- Create: `frontend/src/components/chat/ThreadSidebar.tsx`

**Interfaces:**
- Consumes: `chatApi`, React Router params, protected route wrapper
- Produces routes:
  - `/app`
  - `/app/chats/:threadId`

- [ ] **Step 1: Create thread sidebar component**

Create `frontend/src/components/chat/ThreadSidebar.tsx`:

```tsx
import { Plus } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import type { ChatThread } from '@/lib/chat-api'

type ThreadSidebarProps = {
  threads: ChatThread[]
  creating: boolean
  onCreateThread: () => Promise<void>
}

export function ThreadSidebar({ threads, creating, onCreateThread }: ThreadSidebarProps) {
  const { threadId } = useParams()

  return (
    <aside className="flex h-full w-72 shrink-0 flex-col border-r bg-background">
      <div className="flex h-14 items-center justify-between border-b px-4">
        <span className="text-sm font-medium">Chats</span>
        <Button size="sm" variant="outline" onClick={() => void onCreateThread()} disabled={creating}>
          <Plus className="size-4" />
        </Button>
      </div>
      <nav className="flex-1 overflow-y-auto p-2">
        {threads.map((thread) => (
          <Link
            key={thread.id}
            to={`/app/chats/${thread.id}`}
            className={
              thread.id === threadId
                ? 'block rounded-md bg-muted px-3 py-2 text-sm font-medium'
                : 'block rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-muted'
            }
          >
            {thread.title || 'Untitled chat'}
          </Link>
        ))}
      </nav>
    </aside>
  )
}
```

- [ ] **Step 2: Create route container**

Create `frontend/src/pages/ChatPage.tsx`:

```tsx
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { ChatThread as ChatThreadView } from '@/components/chat/ChatThread'
import { ThreadSidebar } from '@/components/chat/ThreadSidebar'
import { chatApi, type ChatThread } from '@/lib/chat-api'

export function ChatPage() {
  const { threadId } = useParams()
  const navigate = useNavigate()
  const [threads, setThreads] = useState<ChatThread[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function loadThreads() {
    setLoading(true)
    setError(null)
    try {
      setThreads(await chatApi.listThreads())
    } catch (unknownError) {
      setError(unknownError instanceof Error ? unknownError.message : 'Failed to load chats')
    } finally {
      setLoading(false)
    }
  }

  async function createThread() {
    setCreating(true)
    setError(null)
    try {
      const thread = await chatApi.createThread(null)
      setThreads((current) => [thread, ...current])
      navigate(`/app/chats/${thread.id}`)
    } catch (unknownError) {
      setError(unknownError instanceof Error ? unknownError.message : 'Failed to create chat')
    } finally {
      setCreating(false)
    }
  }

  useEffect(() => {
    void loadThreads()
  }, [])

  return (
    <main className="flex h-screen bg-background text-foreground">
      <ThreadSidebar threads={threads} creating={creating} onCreateThread={createThread} />
      <section className="flex min-w-0 flex-1 flex-col">
        {loading ? (
          <div className="p-6 text-sm text-muted-foreground">Loading chats...</div>
        ) : error ? (
          <div className="p-6 text-sm text-destructive">{error}</div>
        ) : threadId ? (
          <ChatThreadView threadId={threadId} onMessageCommitted={loadThreads} />
        ) : (
          <div className="flex flex-1 items-center justify-center p-6 text-sm text-muted-foreground">
            Create or select a chat.
          </div>
        )}
      </section>
    </main>
  )
}
```

- [ ] **Step 3: Wire routes**

Modify `frontend/src/App.tsx`:

```tsx
import { ChatPage } from '@/pages/ChatPage'

<Route element={<ProtectedRoute />}>
  <Route path="/app" element={<ChatPage />} />
  <Route path="/app/chats/:threadId" element={<ChatPage />} />
</Route>
```

---

### Task 7: Frontend Chat Thread UI

**Files:**
- Create: `frontend/src/components/chat/message-format.ts`
- Create: `frontend/src/components/chat/ChatThread.tsx`

**Interfaces:**
- Consumes: `chatApi.listMessages`, `createChatTransport`, `useChat`
- Produces: `ChatThread({ threadId, onMessageCommitted }: { threadId: string; onMessageCommitted: () => void | Promise<void> })`

- [ ] **Step 1: Add message conversion helpers**

Create `frontend/src/components/chat/message-format.ts`:

```ts
import type { ChatMessage } from '@/lib/chat-api'

export type InitialChatMessage = {
  id: string
  role: 'user' | 'assistant'
  parts: Array<{ type: 'text'; text: string }>
}

export function toInitialChatMessage(message: ChatMessage): InitialChatMessage {
  return {
    id: message.id,
    role: message.role,
    parts: [{ type: 'text', text: message.content }],
  }
}

export function messageText(message: { parts?: Array<{ type: string; text?: string }> }) {
  return message.parts?.map((part) => (part.type === 'text' ? part.text ?? '' : '')).join('') ?? ''
}
```

- [ ] **Step 2: Build chat thread component**

Create `frontend/src/components/chat/ChatThread.tsx`:

```tsx
import { Send } from 'lucide-react'
import { FormEvent, useEffect, useMemo, useState } from 'react'
import { useChat } from '@ai-sdk/react'

import { Button } from '@/components/ui/button'
import { messageText, toInitialChatMessage, type InitialChatMessage } from '@/components/chat/message-format'
import { chatApi } from '@/lib/chat-api'
import { createChatTransport } from '@/lib/chat-stream'

type ChatThreadProps = {
  threadId: string
  onMessageCommitted: () => void | Promise<void>
}

export function ChatThread({ threadId, onMessageCommitted }: ChatThreadProps) {
  const [initialMessages, setInitialMessages] = useState<InitialChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loadingHistory, setLoadingHistory] = useState(true)
  const [historyError, setHistoryError] = useState<string | null>(null)
  const transport = useMemo(() => createChatTransport(), [])
  const { messages, sendMessage, status, error, setMessages } = useChat({
    id: threadId,
    messages: initialMessages,
    transport,
  })

  useEffect(() => {
    let cancelled = false
    async function loadMessages() {
      setLoadingHistory(true)
      setHistoryError(null)
      try {
        const rows = await chatApi.listMessages(threadId)
        if (cancelled) return
        const converted = rows.map(toInitialChatMessage)
        setInitialMessages(converted)
        setMessages(converted)
      } catch (unknownError) {
        if (!cancelled) {
          setHistoryError(unknownError instanceof Error ? unknownError.message : 'Failed to load messages')
        }
      } finally {
        if (!cancelled) setLoadingHistory(false)
      }
    }
    void loadMessages()
    return () => {
      cancelled = true
    }
  }, [threadId, setMessages])

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const text = input.trim()
    if (!text || status === 'streaming' || status === 'submitted') return
    setInput('')
    await sendMessage({ text }, { body: { threadId } })
    await onMessageCommitted()
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex h-14 items-center border-b px-5 text-sm font-medium">Document Copilot</div>
      <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
        {loadingHistory ? (
          <p className="text-sm text-muted-foreground">Loading messages...</p>
        ) : historyError ? (
          <p className="text-sm text-destructive">{historyError}</p>
        ) : messages.length === 0 ? (
          <p className="text-sm text-muted-foreground">Ask a question about the filing corpus.</p>
        ) : (
          <div className="space-y-4">
            {messages.map((message) => (
              <div key={message.id} className={message.role === 'user' ? 'flex justify-end' : 'flex justify-start'}>
                <div className="max-w-3xl rounded-md border px-4 py-3 text-sm">
                  {messageText(message)}
                </div>
              </div>
            ))}
          </div>
        )}
        {error ? <p className="mt-4 text-sm text-destructive">{error.message}</p> : null}
      </div>
      <form onSubmit={submit} className="flex gap-2 border-t p-4">
        <input
          className="min-w-0 flex-1 rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="Ask about a filing..."
        />
        <Button type="submit" disabled={!input.trim() || status === 'streaming' || status === 'submitted'}>
          <Send className="size-4" />
        </Button>
      </form>
    </div>
  )
}
```

- [ ] **Step 3: Type-check and adjust AI SDK types**

Run:

```bash
cd frontend
pnpm tsc --noEmit
```

Expected: exit code 0. If `useChat` expects a version-specific message type name, keep `InitialChatMessage` local to `message-format.ts` and adjust only the conversion shape needed by the installed `@ai-sdk/react` version.

---

### Task 8: Full Verification

**Files:**
- Modify only files listed in Tasks 1-7.

**Interfaces:**
- Consumes all Phase 3 route and UI contracts.
- Produces a verified local vertical slice.

- [ ] **Step 1: Run backend unit tests**

Run:

```bash
cd backend
uv run pytest -m "not integration"
```

Expected: exit code 0 and no network calls except tests that explicitly mock auth.

- [ ] **Step 2: Run frontend static checks**

Run:

```bash
cd frontend
pnpm tsc --noEmit
pnpm lint
pnpm build
```

Expected: all commands exit 0.

- [ ] **Step 3: Run backend and frontend locally**

Start backend:

```bash
cd backend
uv run uvicorn app.main:app --reload --port 8000
```

Start frontend:

```bash
cd frontend
pnpm dev
```

Expected: backend serves `GET /health` on `http://127.0.0.1:8000/health`; frontend serves the SPA on the Vite URL.

- [ ] **Step 4: Manual vertical-slice check**

In the browser:

1. Sign in with Supabase email auth.
2. Open `/app`.
3. Create a chat.
4. Send `Across Apple filings, what changed in Services revenue mix?`.
5. Confirm text streams into the assistant message.
6. Refresh the page.
7. Confirm the user message and assistant stub response reload from `chat_messages`.

Expected: the answer is clearly a stub and does not claim retrieval or citations exist.

- [ ] **Step 5: Authorization check**

Call another user's thread ID with the current user's token:

```bash
curl -i \
  -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN" \
  http://127.0.0.1:8000/chat/threads/$OTHER_USER_THREAD_ID/messages
```

Expected: `403 Forbidden`.

- [ ] **Step 6: Diff hygiene**

Run:

```bash
git diff --check
git status --short
```

Expected: no whitespace errors and only Phase 3 files changed.

---

## Phase 3 Exit Criteria

- Authenticated users can create and view their own chat threads.
- Authenticated users cannot read another user's thread.
- A submitted chat message reaches FastAPI with the Supabase bearer token.
- FastAPI streams a stub assistant response.
- User and assistant messages persist after the stream request.
- Refreshing a thread reloads message history.
- The UI makes no citation or retrieval claims.
- Backend fast tests pass.
- Frontend type-check, lint, and production build pass.
