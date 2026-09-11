"""add salesperson_accounts table (approval gate for real sign-ins)

Revision ID: d3e4f5a6b7c8
Revises: c7d8e9f0a1b2
Create Date: 2026-09-11 00:00:00.000000

Gates a real Supabase Auth sign-in behind approval — see
app/models/salesperson_account.py.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd3e4f5a6b7c8'
down_revision: Union[str, Sequence[str], None] = 'c7d8e9f0a1b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'salesperson_accounts',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('supabase_user_id', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column(
            'status',
            sa.Enum('PENDING', 'APPROVED', 'REJECTED', name='salespersonaccountstatus', native_enum=False),
            nullable=False,
        ),
        sa.Column('approved_by', sa.String(length=255), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('supabase_user_id'),
    )
    op.create_index(
        op.f('ix_salesperson_accounts_supabase_user_id'),
        'salesperson_accounts',
        ['supabase_user_id'],
        unique=True,
    )

    # Extend the RLS defense-in-depth groundwork from
    # c7d8e9f0a1b2_add_rls_defense_in_depth.py to this new table — same
    # inert-until-cutover reasoning applies (see that migration's docstring).
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            DO $$
            BEGIN
                IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_runtime') THEN
                    GRANT SELECT, INSERT, UPDATE, DELETE ON salesperson_accounts TO app_runtime;
                END IF;
            END
            $$;
            """
        )
        op.execute('ALTER TABLE "salesperson_accounts" ENABLE ROW LEVEL SECURITY;')
        op.execute('ALTER TABLE "salesperson_accounts" FORCE ROW LEVEL SECURITY;')
        op.execute('DROP POLICY IF EXISTS require_authenticated_session ON "salesperson_accounts";')
        op.execute(
            """CREATE POLICY require_authenticated_session ON "salesperson_accounts"
                USING (current_setting('app.authenticated', true) = 'true')
                WITH CHECK (current_setting('app.authenticated', true) = 'true');"""
        )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute('DROP POLICY IF EXISTS require_authenticated_session ON "salesperson_accounts";')
        op.execute('ALTER TABLE "salesperson_accounts" NO FORCE ROW LEVEL SECURITY;')
        op.execute('ALTER TABLE "salesperson_accounts" DISABLE ROW LEVEL SECURITY;')
    op.drop_index(op.f('ix_salesperson_accounts_supabase_user_id'), table_name='salesperson_accounts')
    op.drop_table('salesperson_accounts')
