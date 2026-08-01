from sqlalchemy import inspect

from app.database.models import Base

EXPECTED_TABLES = {
    "users",
    "source_documents",
    "document_chunks",
    "chat_threads",
    "chat_messages",
    "message_citations",
}


def test_metadata_contains_phase_one_tables() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_chat_records_are_connected_to_their_owner_and_thread() -> None:
    thread_foreign_keys = {
        foreign_key.target_fullname
        for foreign_key in Base.metadata.tables["chat_threads"].foreign_keys
    }
    message_foreign_keys = {
        foreign_key.target_fullname
        for foreign_key in Base.metadata.tables["chat_messages"].foreign_keys
    }

    assert thread_foreign_keys == {"users.id"}
    assert message_foreign_keys == {"chat_threads.id"}


def test_citations_connect_messages_to_retrieved_chunks() -> None:
    citation_foreign_keys = {
        foreign_key.target_fullname
        for foreign_key in Base.metadata.tables["message_citations"].foreign_keys
    }

    assert citation_foreign_keys == {"chat_messages.id", "document_chunks.id"}


def test_document_chunks_are_configured_for_hybrid_retrieval() -> None:
    columns = inspect(Base.metadata.tables["document_chunks"]).columns

    assert columns["embedding"].type.dim == 1536
    assert columns["search_vector"].computed is not None
    assert "to_tsvector" in str(columns["search_vector"].computed.sqltext)
