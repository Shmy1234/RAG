from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient

from app.api.chat import (
    get_agent_runner,
    get_chat_store,
    get_document_retriever,
    get_grounding_validator,
)
from app.assistant.outputs import GroundedAnswer
from app.auth.dependencies import AuthenticatedUser, get_current_user
from app.chat.stub_stream import build_stub_reply
from app.database.chats import ForbiddenThreadError, ThreadNotFoundError
from app.main import app


@pytest.fixture
def user() -> AuthenticatedUser:
    return AuthenticatedUser(id=uuid4(), email="analyst@equity-research-assistant.example")


class MemoryChatStore:
    def __init__(self):
        self.thread_id = uuid4()
        self.owner_id: UUID | None = None
        self.messages: list[dict[str, object]] = []
        self.ensured_users: list[tuple[UUID, str | None]] = []

    async def ensure_user(self, user_id: UUID, email: str | None):
        self.ensured_users.append((user_id, email))

    async def list_threads(self, user_id: UUID):
        if self.owner_id != user_id:
            return []
        now = datetime.now(UTC).isoformat()
        return [
            {
                "id": str(self.thread_id),
                "title": None,
                "created_at": now,
                "updated_at": now,
            }
        ]

    async def create_thread(self, user_id: UUID, title: str | None):
        self.owner_id = user_id
        now = datetime.now(UTC).isoformat()
        return {
            "id": str(self.thread_id),
            "title": title,
            "created_at": now,
            "updated_at": now,
        }

    async def get_thread(self, user_id: UUID, thread_id: UUID):
        if thread_id != self.thread_id:
            raise ThreadNotFoundError()
        if self.owner_id != user_id:
            raise ForbiddenThreadError()
        return {"id": str(thread_id), "user_id": str(user_id)}

    async def list_messages(self, user_id: UUID, thread_id: UUID):
        await self.get_thread(user_id, thread_id)
        return self.messages

    async def append_message(self, thread_id: UUID, role: str, content: str, message_data):
        message = {
            "id": str(uuid4()),
            "thread_id": str(thread_id),
            "position": len(self.messages),
            "role": role,
            "content": content,
            "message_data": message_data,
            "created_at": datetime.now(UTC).isoformat(),
        }
        self.messages.append(message)
        return message

    async def append_citations(self, message_id: str, citations):
        return None


class FakeRetriever:
    async def retrieve(self, query: str, **kwargs):
        return []


class FakeAgent:
    async def run(self, prompt: str, *, deps):
        return SimpleNamespace(output=GroundedAnswer(answer=build_stub_reply(prompt)))


class FakeGroundingValidator:
    def validate(self, answer, passages):
        return answer


@pytest.fixture
def store() -> MemoryChatStore:
    return MemoryChatStore()


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_threads_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/chat/threads")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.anyio
async def test_create_thread_returns_thread(user, store):
    async def override_user():
        return user

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_chat_store] = lambda: store

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/chat/threads", json={"title": "Apple revenue mix"})

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["title"] == "Apple revenue mix"
    assert store.ensured_users == [(user.id, user.email)]


@pytest.mark.anyio
async def test_stream_persists_messages_and_returns_stub(user, store):
    async def override_user():
        return user

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_chat_store] = lambda: store
    app.dependency_overrides[get_document_retriever] = lambda: FakeRetriever()
    app.dependency_overrides[get_agent_runner] = lambda: FakeAgent()
    app.dependency_overrides[get_grounding_validator] = lambda: FakeGroundingValidator()
    await store.create_thread(user.id, "Apple revenue mix")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/chat/stream",
            json={
                "threadId": str(store.thread_id),
                "messages": [{"role": "user", "content": "What changed?"}],
            },
        )

    assert response.status_code == status.HTTP_200_OK
    assert '"type": "text-delta"' in response.text
    assert '"type": "finish"' in response.text
    assert [message["role"] for message in store.messages] == ["user", "assistant"]


@pytest.mark.anyio
async def test_messages_returns_forbidden_for_another_users_thread(user, store):
    other_user = AuthenticatedUser(id=uuid4(), email="other@equity-research-assistant.example")
    await store.create_thread(other_user.id, "Private")

    async def override_user():
        return user

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_chat_store] = lambda: store

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/chat/threads/{store.thread_id}/messages")

    assert response.status_code == status.HTTP_403_FORBIDDEN
