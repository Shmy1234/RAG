"""Add concurrency-safe atomic chat persistence functions.

Revision ID: 0003_atomic_chat_persistence
Revises: 0002_enable_rls_unrestricted
"""

from alembic import op

revision = "0003_atomic_chat_persistence"
down_revision = "0002_enable_rls_unrestricted"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION append_chat_message_atomic(
            p_thread_id uuid,
            p_role text,
            p_content text,
            p_message_data jsonb
        ) RETURNS SETOF chat_messages
        LANGUAGE plpgsql
        SECURITY INVOKER
        SET search_path = public
        AS $$
        DECLARE
            v_position integer;
            v_message_id uuid;
        BEGIN
            PERFORM id FROM chat_threads WHERE id = p_thread_id FOR UPDATE;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'chat thread % does not exist', p_thread_id
                    USING ERRCODE = '23503';
            END IF;

            SELECT COALESCE(MAX(position), -1) + 1
            INTO v_position
            FROM chat_messages
            WHERE thread_id = p_thread_id;

            INSERT INTO chat_messages (thread_id, position, role, content, message_data)
            VALUES (p_thread_id, v_position, p_role, p_content, p_message_data)
            RETURNING id INTO v_message_id;

            RETURN QUERY SELECT * FROM chat_messages WHERE id = v_message_id;
        END;
        $$;

        REVOKE ALL ON FUNCTION append_chat_message_atomic(uuid, text, text, jsonb)
            FROM PUBLIC, anon, authenticated;
        GRANT EXECUTE ON FUNCTION append_chat_message_atomic(uuid, text, text, jsonb)
            TO service_role;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION append_grounded_answer_atomic(
            p_thread_id uuid,
            p_content text,
            p_message_data jsonb,
            p_citations jsonb
        ) RETURNS SETOF chat_messages
        LANGUAGE plpgsql
        SECURITY INVOKER
        SET search_path = public
        AS $$
        DECLARE
            v_position integer;
            v_message_id uuid;
        BEGIN
            PERFORM id FROM chat_threads WHERE id = p_thread_id FOR UPDATE;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'chat thread % does not exist', p_thread_id
                    USING ERRCODE = '23503';
            END IF;

            SELECT COALESCE(MAX(position), -1) + 1
            INTO v_position
            FROM chat_messages
            WHERE thread_id = p_thread_id;

            INSERT INTO chat_messages (thread_id, position, role, content, message_data)
            VALUES (p_thread_id, v_position, 'assistant', p_content, p_message_data)
            RETURNING id INTO v_message_id;

            INSERT INTO message_citations (
                message_id,
                chunk_id,
                citation_index,
                quoted_text
            )
            SELECT
                v_message_id,
                (citation ->> 'chunk_id')::uuid,
                (citation ->> 'citation_index')::integer,
                citation ->> 'quoted_text'
            FROM jsonb_array_elements(p_citations) AS citation;

            RETURN QUERY SELECT * FROM chat_messages WHERE id = v_message_id;
        END;
        $$;

        REVOKE ALL ON FUNCTION append_grounded_answer_atomic(uuid, text, jsonb, jsonb)
            FROM PUBLIC, anon, authenticated;
        GRANT EXECUTE ON FUNCTION append_grounded_answer_atomic(uuid, text, jsonb, jsonb)
            TO service_role;
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP FUNCTION IF EXISTS append_grounded_answer_atomic(uuid, text, jsonb, jsonb)"
    )
    op.execute("DROP FUNCTION IF EXISTS append_chat_message_atomic(uuid, text, text, jsonb)")
