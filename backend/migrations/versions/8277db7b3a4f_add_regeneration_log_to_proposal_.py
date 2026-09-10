"""add regeneration log to proposal sections

Revision ID: 8277db7b3a4f
Revises: 209e98a651b7
Create Date: 2026-09-10 14:23:15.559809

Phase 4 (section regeneration) — see docs/decisions.md #13b: a per-section
instruction trail so the salesperson's regeneration intent across attempts
isn't lost/re-typed from memory. JSON list, append-only from the app's
perspective, default empty for both new rows and the backfill of existing
sections.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8277db7b3a4f'
down_revision: Union[str, Sequence[str], None] = '209e98a651b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'proposal_sections',
        sa.Column(
            'regeneration_log',
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('proposal_sections', 'regeneration_log')
