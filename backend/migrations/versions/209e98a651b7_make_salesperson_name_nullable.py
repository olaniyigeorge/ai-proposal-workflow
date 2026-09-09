"""make salesperson_name nullable (unassigned when client fills form directly)

Revision ID: 209e98a651b7
Revises: e10f37eda6f1
Create Date: 2026-09-09 18:00:00.000000

See docs/decisions.md #20 and docs/edge-cases.md "Salesperson attribution
breaks when the client fills the form": the client can submit the intake
form with no salesperson on the call at all, so the field must allow NULL
("unassigned") rather than forcing a placeholder value.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '209e98a651b7'
down_revision: Union[str, Sequence[str], None] = 'e10f37eda6f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('proposals') as batch_op:
        batch_op.alter_column(
            'salesperson_name',
            existing_type=sa.String(length=255),
            nullable=True,
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('proposals') as batch_op:
        batch_op.alter_column(
            'salesperson_name',
            existing_type=sa.String(length=255),
            nullable=False,
        )
