"""add display_name to salesperson_accounts

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-09-11 00:00:00.000000

Lets a salesperson set their own display name (self-service), used when
self-claiming an unassigned proposal — see app/models/salesperson_account.py.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e4f5a6b7c8d9'
down_revision: Union[str, Sequence[str], None] = 'd3e4f5a6b7c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'salesperson_accounts', sa.Column('display_name', sa.String(length=255), nullable=True)
    )
    op.create_unique_constraint(
        'uq_salesperson_accounts_display_name', 'salesperson_accounts', ['display_name']
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        'uq_salesperson_accounts_display_name', 'salesperson_accounts', type_='unique'
    )
    op.drop_column('salesperson_accounts', 'display_name')
