"""add delivery records table

Revision ID: 25690026d816
Revises: 6f7286ec6d1e
Create Date: 2026-09-10 18:54:06.897645

Phase 7 (client delivery): one row per delivery attempt (not unique per
proposal — a failed delivery can be retried, each attempt gets its own row).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '25690026d816'
down_revision: Union[str, Sequence[str], None] = '6f7286ec6d1e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'delivery_records',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('proposal_id', sa.Uuid(), nullable=False),
        sa.Column(
            'status',
            sa.Enum('SENT', 'FAILED', 'BOUNCED', name='deliverystatus', native_enum=False),
            nullable=False,
        ),
        sa.Column('recipient_email', sa.String(length=255), nullable=False),
        sa.Column('subject', sa.String(length=500), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['proposal_id'], ['proposals.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_delivery_records_proposal_id'), 'delivery_records', ['proposal_id'], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_delivery_records_proposal_id'), table_name='delivery_records')
    op.drop_table('delivery_records')
