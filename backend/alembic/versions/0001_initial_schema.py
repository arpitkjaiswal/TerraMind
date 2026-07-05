"""initial_schema

Revision ID: 0001
Revises: 
Create Date: 2026-07-05 15:35:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    # ENUMS
    user_role = postgresql.ENUM('farmer', 'agronomist', 'admin', name='user_role')
    user_role.create(op.get_bind())
    
    source_type = postgresql.ENUM('pdf', 'photo', 'csv', name='source_type')
    source_type.create(op.get_bind())
    
    ingest_status = postgresql.ENUM('pending_ocr', 'pending_review', 'processing', 'ready', 'ingest_failed', name='ingest_status')
    ingest_status.create(op.get_bind())
    
    confidence_label = postgresql.ENUM('documented_fact', 'statistical_association', 'unconfirmed_hypothesis', name='confidence_label')
    confidence_label.create(op.get_bind())
    
    edge_type = postgresql.ENUM('APPLIED_TO', 'OCCURRED_DURING', 'PRECEDED', 'CORRELATED_WITH', 'CONFIRMED_CAUSE', name='edge_type')
    edge_type.create(op.get_bind())
    
    # TABLES
    op.create_table('farms',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('owner_user_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table('plots',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('farm_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('geo_boundary', sa.Text(), nullable=True),
        sa.Column('crop_type', sa.String(length=255), nullable=False),
        sa.Column('size_ha', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['farm_id'], ['farms.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_plots_farm_created', 'plots', ['farm_id', 'created_at'], unique=False)
    
    op.create_table('users',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('farm_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('email', sa.String(length=320), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('role', postgresql.ENUM('farmer', 'agronomist', 'admin', name='user_role', create_type=False), nullable=False),
        sa.Column('auth_provider_id', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['farm_id'], ['farms.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    
    op.create_table('documents',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('farm_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('plot_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('source_type', postgresql.ENUM('pdf', 'photo', 'csv', name='source_type', create_type=False), nullable=False),
        sa.Column('label', sa.String(length=512), nullable=False),
        sa.Column('storage_uri', sa.String(length=1024), nullable=False),
        sa.Column('content_hash', sa.String(length=64), nullable=True),
        sa.Column('ingest_status', postgresql.ENUM('pending_ocr', 'pending_review', 'processing', 'ready', 'ingest_failed', name='ingest_status', create_type=False), nullable=False),
        sa.Column('ingest_error', sa.Text(), nullable=True),
        sa.Column('source_confidence', sa.Float(), nullable=True),
        sa.Column('extracted_text', sa.Text(), nullable=True),
        sa.Column('date_of_event', sa.String(length=10), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['plot_id'], ['plots.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_documents_content_hash'), 'documents', ['content_hash'], unique=False)
    op.create_index('ix_documents_farm_status', 'documents', ['farm_id', 'ingest_status'], unique=False)
    op.create_index('ix_documents_plot_created', 'documents', ['plot_id', 'uploaded_at'], unique=False)
    
    op.create_table('query_logs',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('farm_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('plot_id', postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column('query_text', sa.Text(), nullable=False),
        sa.Column('answer_text', sa.Text(), nullable=True),
        sa.Column('confidence_label', postgresql.ENUM('documented_fact', 'statistical_association', 'unconfirmed_hypothesis', name='confidence_label', create_type=False), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('graph_hops', sa.Integer(), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('cache_hit', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['plot_id'], ['plots.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_queries_farm_created', 'query_logs', ['farm_id', 'created_at'], unique=False)
    op.create_index('ix_queries_plot_created', 'query_logs', ['plot_id', 'created_at'], unique=False)
    
    op.create_table('evidence_edges',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('query_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('source_document_id', postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column('graph_node_id', sa.String(length=255), nullable=False),
        sa.Column('node_label', sa.String(length=512), nullable=False),
        sa.Column('node_type', sa.String(length=64), nullable=False),
        sa.Column('relationship_type', postgresql.ENUM('APPLIED_TO', 'OCCURRED_DURING', 'PRECEDED', 'CORRELATED_WITH', 'CONFIRMED_CAUSE', name='edge_type', create_type=False), nullable=False),
        sa.Column('date', sa.String(length=10), nullable=True),
        sa.ForeignKeyConstraint(['query_id'], ['query_logs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_document_id'], ['documents.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table('corrections',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('evidence_edge_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('corrected_by_user_id', postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column('correction_note', sa.Text(), nullable=False),
        sa.Column('memify_queued', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['corrected_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['evidence_edge_id'], ['evidence_edges.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

def downgrade() -> None:
    op.drop_table('corrections')
    op.drop_table('evidence_edges')
    op.drop_table('query_logs')
    op.drop_table('documents')
    op.drop_table('users')
    op.drop_table('plots')
    op.drop_table('farms')
    
    postgresql.ENUM(name='edge_type').drop(op.get_bind())
    postgresql.ENUM(name='confidence_label').drop(op.get_bind())
    postgresql.ENUM(name='ingest_status').drop(op.get_bind())
    postgresql.ENUM(name='source_type').drop(op.get_bind())
    postgresql.ENUM(name='user_role').drop(op.get_bind())
