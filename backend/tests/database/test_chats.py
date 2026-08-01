from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.database.chats import ChatStore, ForbiddenThreadError, ThreadNotFoundError


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, rows: list[dict[str, object]], insert_rows: list[dict[str, object]]):
        self.rows = rows
        self.insert_rows = insert_rows
        self.filters: dict[str, object] = {}
        self.reverse = False
        self.order_key: str | None = None
        self.limit_count: int | None = None
        self.insert_payload: dict[str, object] | None = None

    def select(self, _columns: str):
        return self

    def eq(self, key: str, value: object):
        self.filters[key] = value
        return self

    def order(self, key: str, desc: bool = False):
        self.order_key = key
        self.reverse = desc
        return self

    def limit(self, count: int):
        self.limit_count = count
        return self

    def insert(self, payload: dict[str, object]):
        self.insert_payload = payload
        return self

    def upsert(self, payload: dict[str, object], on_conflict: str):
        self.insert_payload = payload
        return self

    def execute(self):
        if self.insert_payload is not None:
            now = datetime.now(UTC).isoformat()
            row = {"id": str(uuid4()), "created_at": now, **self.insert_payload}
            self.insert_rows.append(row)
            return FakeResponse([row])

        rows = [
            row
            for row in self.rows
            if all(str(row.get(key)) == str(value) for key, value in self.filters.items())
        ]
        if self.order_key is not None:
            rows.sort(key=lambda row: row[self.order_key], reverse=self.reverse)
        if self.limit_count is not None:
            rows = rows[: self.limit_count]
        return FakeResponse(rows)


class FakeClient:
    def __init__(self, tables: dict[str, list[dict[str, object]]]):
        self.tables = tables

    def table(self, name: str):
        rows = self.tables.setdefault(name, [])
        return FakeQuery(rows, rows)


@pytest.fixture
def ids() -> tuple[UUID, UUID, UUID]:
    return uuid4(), uuid4(), uuid4()


@pytest.mark.anyio
async def test_chat_store_lists_only_threads_owned_by_user(ids) -> None:
    user_id, other_user_id, thread_id = ids
    client = FakeClient(
        {
            "chat_threads": [
                {
                    "id": str(thread_id),
                    "user_id": str(user_id),
                    "title": "Owned",
                    "updated_at": "2026-01-02T00:00:00+00:00",
                },
                {
                    "id": str(uuid4()),
                    "user_id": str(other_user_id),
                    "title": "Other",
                    "updated_at": "2026-01-03T00:00:00+00:00",
                },
            ]
        }
    )

    rows = await ChatStore(client).list_threads(user_id)

    assert [row["title"] for row in rows] == ["Owned"]


@pytest.mark.anyio
async def test_chat_store_ensures_authenticated_user_profile(ids) -> None:
    user_id, _other_user_id, _thread_id = ids
    client = FakeClient({"users": []})

    await ChatStore(client).ensure_user(user_id, "analyst@equity-research-assistant.example")

    assert client.tables["users"][0]["id"] == str(user_id)
    assert client.tables["users"][0]["email"] == "analyst@equity-research-assistant.example"


@pytest.mark.anyio
async def test_chat_store_rejects_thread_owned_by_another_user(ids) -> None:
    user_id, other_user_id, thread_id = ids
    client = FakeClient(
        {
            "chat_threads": [{"id": str(thread_id), "user_id": str(other_user_id)}]
        }
    )

    with pytest.raises(ForbiddenThreadError):
        await ChatStore(client).get_thread(user_id, thread_id)


@pytest.mark.anyio
async def test_chat_store_appends_message_after_existing_position(ids) -> None:
    _user_id, _other_user_id, thread_id = ids
    client = FakeClient(
        {
            "chat_messages": [
                {"thread_id": str(thread_id), "position": 0},
                {"thread_id": str(thread_id), "position": 1},
            ]
        }
    )

    row = await ChatStore(client).append_message(
        thread_id, "assistant", "Hello", {"phase": 3}
    )

    assert row["position"] == 2
    assert row["content"] == "Hello"


@pytest.mark.anyio
async def test_chat_store_raises_not_found_for_unknown_thread(ids) -> None:
    user_id, _other_user_id, thread_id = ids

    with pytest.raises(ThreadNotFoundError):
        await ChatStore(FakeClient({"chat_threads": []})).get_thread(user_id, thread_id)


@pytest.mark.anyio
async def test_chat_store_persists_message_citations(ids) -> None:
    _user_id, _other_user_id, thread_id = ids
    client = FakeClient({"message_citations": []})

    await ChatStore(client).append_citations(
        str(thread_id),
        [
            {
                "chunk_id": str(uuid4()),
                "citation_index": 0,
                "quoted_text": "Services revenue increased.",
            }
        ],
    )

    assert client.tables["message_citations"][0]["message_id"] == str(thread_id)
    assert client.tables["message_citations"][0]["citation_index"] == 0
