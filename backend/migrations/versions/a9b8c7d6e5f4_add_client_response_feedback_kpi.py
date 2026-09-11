"""
add client response records, feedback entries, and KPI support.

Revision ID: a9b8c7d6e5f4
Revises: 25690026d816
Create Date: 2026-09-11 10:00:00.000000

Phase 10 (week-3 feature work):
- client_response_records: unauthenticated client accept/decline/feedback on a
  proposal, linked to the proposal. Captures response_type + optional feedback
  text; also stores the client_ip for light abuse-signal (never stored as PII
  beyond the request path).
- feedback_entries: salesperson feedback about the system (category + text),
  auth-required.
- Adds client_response_records.proposal FK + indexes; feedback_entries has no
  FK (anonymous-ish, tied to actor email only).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a9b8c7d6e5f4'
down_revision: Union[str, Sequence[str], None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'client_response_records',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('proposal_id', sa.Uuid(), nullable=False),
        sa.Column(
            'response_type',
            sa.Enum('ACCEPTED', 'DECLINED', 'NO_RESPONSE', name='clientresponsetype', native_enum=False),
            nullable=False,
        ),
        sa.Column('feedback_text', sa.Text(), nullable=True),
        sa.Column('client_ip', sa.String(length=45), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['proposal_id'], ['proposals.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_client_response_records_proposal_id'),
        'client_response_records', ['proposal_id'], unique=False,
    )
    op.create_index(
        op.f('ix_client_response_records_created_at'),
        'client_response_records', ['created_at'], unique=False,
    )

    op.create_table(
        'feedback_entries',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column(
            'category',
            sa.Enum('BUG', 'FEATURE_REQUEST', 'GENERAL', name='feedbackcategory', native_enum=False),
            nullable=False,
        ),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('actor_email', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_feedback_entries_category'),
        'feedback_entries', ['category'], unique=False,
    )
    op.create_index(
        op.f('ix_feedback_entries_created_at'),
        'feedback_entries', ['created_at'], unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_feedback_entries_created_at'), table_name='feedback_entries')
    op.drop_index(op.f('ix_feedback_entries_category'), table_name='feedback_entries')
    op.drop_table('feedback_entries')
    op.drop_index(op.f('ix_client_response_records_created_at'), table_name='client_response_records')
    op.drop_index(op.f('ix_client_response_records_proposal_id'), table_name='client_response_records')
    op.drop_table('client_response_records')
