"""add claude call logs table

Revision ID: b637bee3715a
Revises: 8277db7b3a4f
Create Date: 2026-09-10 15:29:39.231968

Observability table: one row per Claude API call (full-generation or
regeneration) — prompts, response, token usage, latency. Nothing else in the
system reads this back; it exists so the team can see what's actually being
sent/spent and improve prompts over time.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b637bee3715a'
down_revision: Union[str, Sequence[str], None] = '8277db7b3a4f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'claude_call_logs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('proposal_id', sa.Uuid(), nullable=False),
        sa.Column('section_key', sa.String(length=64), nullable=False),
        sa.Column(
            'call_type',
            sa.Enum('FULL_GENERATION', 'REGENERATION', name='claudecalltype', native_enum=False),
            nullable=False,
        ),
        sa.Column(
            'status',
            sa.Enum('SUCCEEDED', 'FAILED', name='claudecallstatus', native_enum=False),
            nullable=False,
        ),
        sa.Column('instruction', sa.Text(), nullable=True),
        sa.Column('model', sa.String(length=128), nullable=True),
        sa.Column('system_prompt', sa.Text(), nullable=False),
        sa.Column('user_prompt', sa.Text(), nullable=False),
        sa.Column('response_text', sa.Text(), nullable=True),
        sa.Column('input_tokens', sa.Integer(), nullable=True),
        sa.Column('output_tokens', sa.Integer(), nullable=True),
        sa.Column('stop_reason', sa.String(length=64), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['proposal_id'], ['proposals.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_claude_call_logs_proposal_id'), 'claude_call_logs', ['proposal_id'], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_claude_call_logs_proposal_id'), table_name='claude_call_logs')
    op.drop_table('claude_call_logs')
