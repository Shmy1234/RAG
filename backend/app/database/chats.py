import asyncio
from uuid import UUID

from supabase import Client


class ThreadNotFoundError(Exception):
    pass


class ForbiddenThreadError(Exception):
    pass


class ChatStore:
    def __init__(self, client: Client):
        self.client = client

    async def ensure_user(self, user_id: UUID, email: str) -> None:
        await asyncio.to_thread(
            lambda: (
                self.client.table("users")
                .upsert({"id": str(user_id), "email": email}, on_conflict="id")
                .execute()
            )
        )

    async def list_threads(self, user_id: UUID) -> list[dict[str, object]]:
        response = await asyncio.to_thread(
            lambda: (
                self.client.table("chat_threads")
                .select("id,title,created_at,updated_at")
                .eq("user_id", str(user_id))
                .order("updated_at", desc=True)
                .execute()
            )
        )
        return list(response.data or [])

    async def create_thread(self, user_id: UUID, title: str | None) -> dict[str, object]:
        response = await asyncio.to_thread(
            lambda: (
                self.client.table("chat_threads")
                .insert({"user_id": str(user_id), "title": title})
                .execute()
            )
        )
        return dict(response.data[0])

    async def get_thread(self, user_id: UUID, thread_id: UUID) -> dict[str, object]:
        response = await asyncio.to_thread(
            lambda: (
                self.client.table("chat_threads")
                .select("id,user_id,title,created_at,updated_at")
                .eq("id", str(thread_id))
                .limit(1)
                .execute()
            )
        )
        rows = response.data or []
        if not rows:
            raise ThreadNotFoundError()
        row = dict(rows[0])
        if row["user_id"] != str(user_id):
            raise ForbiddenThreadError()
        return row

    async def list_messages(self, user_id: UUID, thread_id: UUID) -> list[dict[str, object]]:
        await self.get_thread(user_id, thread_id)
        response = await asyncio.to_thread(
            lambda: (
                self.client.table("chat_messages")
                .select("id,thread_id,position,role,content,message_data,created_at")
                .eq("thread_id", str(thread_id))
                .order("position")
                .execute()
            )
        )
        return list(response.data or [])

    async def append_message(
        self,
        thread_id: UUID,
        role: str,
        content: str,
        message_data: dict[str, object],
    ) -> dict[str, object]:
        existing = await asyncio.to_thread(
            lambda: (
                self.client.table("chat_messages")
                .select("position")
                .eq("thread_id", str(thread_id))
                .order("position", desc=True)
                .limit(1)
                .execute()
            )
        )
        next_position = 0
        if existing.data:
            next_position = int(existing.data[0]["position"]) + 1
        response = await asyncio.to_thread(
            lambda: (
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
        )
        return dict(response.data[0])
