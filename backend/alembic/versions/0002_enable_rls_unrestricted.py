"""Enable RLS on tables created outside the initial policy set.

Revision ID: 0002_enable_rls_unrestricted
Revises: 0001_initial_schema
"""

from alembic import op


revision = "0002_enable_rls_unrestricted"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


_TABLES = ("source_documents", "document_chunks", "alembic_version")


def upgrade() -> None:
    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
