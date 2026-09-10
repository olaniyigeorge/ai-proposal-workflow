"""add document artifacts table

Revision ID: 6f7286ec6d1e
Revises: b637bee3715a
Create Date: 2026-09-10 17:51:28.306210

Phase 6 (document generation): the one branded PDF generated per Proposal,
at APPROVED, exactly once — see CLAUDE.md "there is no 'draft PDF'". The
unique constraint on proposal_id is the DB-level backstop for that rule.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6f7286ec6d1e'
down_revision: Union[str, Sequence[str], None] = 'b637bee3715a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'document_artifacts',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('proposal_id', sa.Uuid(), nullable=False),
        sa.Column('storage_path', sa.String(length=500), nullable=False),
        sa.Column('file_size_bytes', sa.Integer(), nullable=False),
        sa.Column('page_count', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['proposal_id'], ['proposals.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('proposal_id'),
    )
    op.create_index(
        op.f('ix_document_artifacts_proposal_id'), 'document_artifacts', ['proposal_id'], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_document_artifacts_proposal_id'), table_name='document_artifacts')
    op.drop_table('document_artifacts')
