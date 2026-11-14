"""job-specific documents (tailored resumes, cover letters)

Revision ID: d4a8b0c2e913
Revises: c3d2ebf1b7a1
Create Date: 2026-11-14 09:00:00
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'd4a8b0c2e913'
down_revision: str | None = 'c3d2ebf1b7a1'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('documents', sa.Column('job_id', sa.Uuid(), nullable=True))
    op.add_column('documents', sa.Column('meta', postgresql.JSONB(astext_type=sa.Text()),
                                         server_default=sa.text("'{}'::jsonb"), nullable=False))
    op.create_index(op.f('ix_documents_job_id'), 'documents', ['job_id'], unique=False)
    op.create_foreign_key('fk_documents_job_id_jobs', 'documents', 'jobs', ['job_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    op.drop_constraint('fk_documents_job_id_jobs', 'documents', type_='foreignkey')
    op.drop_index(op.f('ix_documents_job_id'), table_name='documents')
    op.drop_column('documents', 'meta')
    op.drop_column('documents', 'job_id')
