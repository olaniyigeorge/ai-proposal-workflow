"""add activity log entries table

Revision ID: a1c2d3e4f5a6
Revises: 25690026d816
Create Date: 2026-09-10 00:00:00.000000

Phase 8 (activity logging & audit trail): one append-only row per
state-relevant action across a proposal's lifecycle. See
app/models/activity_log.py for the full rationale.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1c2d3e4f5a6'
down_revision: Union[str, Sequence[str], None] = '25690026d816'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'activity_log_entries',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('proposal_id', sa.Uuid(), nullable=False),
        sa.Column(
            'event_type',
            sa.Enum(
                'CREATED',
                'GENERATED',
                'GENERATION_FAILED',
                'SECTION_EDITED',
                'SECTION_REGENERATED',
                'REGENERATION_FAILED',
                'SECTION_APPROVED',
                'SUBMITTED_FOR_APPROVAL',
                'PROPOSAL_APPROVED',
                'CHANGES_REQUESTED',
                'REJECTED',
                'DOCUMENT_GENERATED',
                'DOCUMENT_GENERATION_FAILED',
                'DELIVERED',
                'DELIVERY_FAILED',
                name='activityeventtype',
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('actor', sa.String(length=255), nullable=True),
        sa.Column('event_metadata', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['proposal_id'], ['proposals.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_activity_log_entries_proposal_id'),
        'activity_log_entries',
        ['proposal_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_activity_log_entries_event_type'),
        'activity_log_entries',
        ['event_type'],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_activity_log_entries_event_type'), table_name='activity_log_entries')
    op.drop_index(op.f('ix_activity_log_entries_proposal_id'), table_name='activity_log_entries')
    op.drop_table('activity_log_entries')
