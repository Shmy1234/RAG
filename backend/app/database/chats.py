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

    async def update_thread_title(
        self,
        user_id: UUID,
        thread_id: UUID,
        title: str,
    ) -> dict[str, object]:
        await self.get_thread(user_id, thread_id)
        response = await asyncio.to_thread(
            lambda: (
                self.client.table("chat_threads")
                .update({"title": title})
                .eq("id", str(thread_id))
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
        response = await asyncio.to_thread(
            lambda: self.client.rpc(
                "append_chat_message_atomic",
                {
                    "p_thread_id": str(thread_id),
                    "p_role": role,
                    "p_content": content,
                    "p_message_data": message_data,
                },
            ).execute()
        )
        return dict(response.data[0])

    async def append_grounded_answer(
        self,
        thread_id: UUID,
        content: str,
        message_data: dict[str, object],
        citations: list[dict[str, object]],
    ) -> dict[str, object]:
        response = await asyncio.to_thread(
            lambda: self.client.rpc(
                "append_grounded_answer_atomic",
                {
                    "p_thread_id": str(thread_id),
                    "p_content": content,
                    "p_message_data": message_data,
                    "p_citations": citations,
                },
            ).execute()
        )
        return dict(response.data[0])

    async def get_citation_source(
        self,
        user_id: UUID,
        message_id: UUID,
        citation_index: int,
    ) -> dict[str, object] | None:
        response = await asyncio.to_thread(
            lambda: (
                self.client.table("message_citations")
                .select(
                    "citation_index,quoted_text,chunk_id,"
                    "chat_messages!inner(id,thread_id,chat_threads!inner(user_id)),"
                    "document_chunks!inner(id,document_id,chunk_index,text,page_number,section,kind,table_id,"
                    "row_start,row_end,source_locator,document_tables(title,units),source_documents!inner("
                    "ticker,company_name,filing_type,filing_date,source_url))"
                )
                .eq("message_id", str(message_id))
                .eq("citation_index", citation_index)
                .eq("chat_messages.chat_threads.user_id", str(user_id))
                .limit(1)
                .execute()
            )
        )
        rows = response.data or []
        if not rows:
            return None

        row = dict(rows[0])
        chunk = row["document_chunks"]

        def fetch_neighbors():
            query = (
                self.client.table("document_chunks")
                .select("id,chunk_index,text,page_number,section,kind")
                .eq("document_id", chunk["document_id"])
                .gte("chunk_index", max(0, chunk["chunk_index"] - 1))
                .lte("chunk_index", chunk["chunk_index"] + 1)
                .neq("id", chunk["id"])
            )
            if chunk.get("table_id") is not None:
                query = query.eq("table_id", chunk["table_id"])
            return query.order("chunk_index").execute()

        neighbors = await asyncio.to_thread(fetch_neighbors)
        row["previous_chunks"] = [
            item for item in (neighbors.data or []) if item["chunk_index"] < chunk["chunk_index"]
        ]
        row["next_chunks"] = [
            item for item in (neighbors.data or []) if item["chunk_index"] > chunk["chunk_index"]
        ]
        return row
