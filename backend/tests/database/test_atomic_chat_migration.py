from pathlib import Path


def test_atomic_chat_migration_locks_threads_and_writes_citations_in_transaction():
    migration = (
        Path(__file__).parents[2]
        / "alembic/versions/0003_atomic_chat_persistence.py"
    ).read_text()

    assert "append_chat_message_atomic" in migration
    assert "append_grounded_answer_atomic" in migration
    assert "FOR UPDATE" in migration
    assert "jsonb_array_elements" in migration
    assert "INSERT INTO message_citations" in migration
    assert "GRANT EXECUTE" in migration
