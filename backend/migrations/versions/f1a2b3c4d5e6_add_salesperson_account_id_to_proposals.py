"""add salesperson_account_id to proposals

Revision ID: f1a2b3c4d5e6
Revises: e4f5a6b7c8d9
Create Date: 2026-09-11 00:00:00.000000

Ownership enforcement (resolved 2026-09-11, see
docs/design-system-redesign-and-ownership-concerns.md §1): a claimed
proposal's owner is now the stable salesperson_accounts.id, not the mutable
salesperson_name string. NULL means unclaimed, same as salesperson_name was
before. ON DELETE SET NULL so removing an account doesn't cascade-delete the
proposals it claimed — it just makes them unowned again.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'e4f5a6b7c8d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'proposals',
        sa.Column('salesperson_account_id', sa.Uuid(), nullable=True),
    )
    op.create_index(
        op.f('ix_proposals_salesperson_account_id'),
        'proposals',
        ['salesperson_account_id'],
        unique=False,
    )
    op.create_foreign_key(
        'fk_proposals_salesperson_account_id_salesperson_accounts',
        'proposals',
        'salesperson_accounts',
        ['salesperson_account_id'],
        ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        'fk_proposals_salesperson_account_id_salesperson_accounts',
        'proposals',
        type_='foreignkey',
    )
    op.drop_index(op.f('ix_proposals_salesperson_account_id'), table_name='proposals')
    op.drop_column('proposals', 'salesperson_account_id')
