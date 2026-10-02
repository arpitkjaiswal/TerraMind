"""Persist both graph endpoints for evidence corrections.

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("evidence_edges", sa.Column("target_graph_node_id", sa.String(length=255), nullable=True))
    # Preserve old rows while enabling the database to arbitrate concurrent uploads.
    op.execute(sa.text("""
        UPDATE documents AS d SET content_hash = NULL
        WHERE d.content_hash IS NOT NULL AND d.id IN (
            SELECT id FROM (
                SELECT id, ROW_NUMBER() OVER (PARTITION BY plot_id, content_hash ORDER BY uploaded_at, id) AS row_num
                FROM documents WHERE content_hash IS NOT NULL
            ) AS duplicates WHERE row_num > 1
        )
    """))
    op.create_index("uq_documents_plot_content_hash", "documents", ["plot_id", "content_hash"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_documents_plot_content_hash", table_name="documents")
    op.drop_column("evidence_edges", "target_graph_node_id")
