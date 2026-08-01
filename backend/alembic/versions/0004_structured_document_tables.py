"""Add structured SEC tables and table-aware chunk provenance.

Revision ID: 0004_structured_document_tables
Revises: 0003_atomic_chat_persistence
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0004_structured_document_tables"
down_revision = "0003_atomic_chat_persistence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_tables",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("table_index", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text()),
        sa.Column("section", sa.Text()),
        sa.Column("units", sa.String(length=100)),
        sa.Column(
            "columns", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column(
            "rows", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column(
            "footnotes", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column(
            "source_locator",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "validation", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["document_id"], ["source_documents.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("document_id", "table_index"),
    )
    op.create_index("ix_document_tables_document_id", "document_tables", ["document_id"])
    op.execute("ALTER TABLE document_tables ENABLE ROW LEVEL SECURITY")

    op.add_column(
        "document_chunks",
        sa.Column("kind", sa.String(length=20), nullable=False, server_default="narrative"),
    )
    op.add_column("document_chunks", sa.Column("table_id", postgresql.UUID(as_uuid=True)))
    op.add_column("document_chunks", sa.Column("row_start", sa.Integer()))
    op.add_column("document_chunks", sa.Column("row_end", sa.Integer()))
    op.add_column(
        "document_chunks",
        sa.Column(
            "source_locator",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.create_foreign_key(
        "fk_document_chunks_table_id",
        "document_chunks",
        "document_tables",
        ["table_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_document_chunks_kind", "document_chunks", ["kind"])
    op.create_index("ix_document_chunks_table_id", "document_chunks", ["table_id"])
    op.alter_column("document_chunks", "kind", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_document_chunks_table_id", table_name="document_chunks")
    op.drop_index("ix_document_chunks_kind", table_name="document_chunks")
    op.drop_constraint("fk_document_chunks_table_id", "document_chunks", type_="foreignkey")
    for column in ("source_locator", "row_end", "row_start", "table_id", "kind"):
        op.drop_column("document_chunks", column)
    op.drop_table("document_tables")
