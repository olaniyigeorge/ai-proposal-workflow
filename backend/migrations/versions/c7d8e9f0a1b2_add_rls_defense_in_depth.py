"""add RLS defense-in-depth groundwork (role + policies, not yet wired up)

Revision ID: c7d8e9f0a1b2
Revises: a1c2d3e4f5a6
Create Date: 2026-09-11 00:00:00.000000

Resolves the RLS half of docs/decisions.md #18 / docs/reference/data-retention-policy.md
"Authorization boundary & defense-in-depth RLS" section — see that doc for
the full reasoning. Summary of what this migration actually does and does
NOT do:

DOES:
- Creates a new, non-owning Postgres role `app_runtime` (LOGIN, NOCREATEDB,
  NOCREATEROLE, NOSUPERUSER) and grants it exactly the table privileges the
  app needs (SELECT/INSERT/UPDATE/DELETE on every app table, USAGE on every
  sequence) — nothing more.
- Enables AND forces row-level security on every app table, with a single
  policy per table: allow the operation only when the session-local flag
  `app.authenticated` is set to `'true'` for that transaction.
- Is safe to run against the live database right now without changing any
  current behavior: this migration is applied by the *existing* connection,
  which owns these tables — Postgres table owners bypass RLS regardless of
  policies (unless `NOSUPERUSER`/ownership itself changes), so nothing
  changes for today's app connection. This migration only lays groundwork.

DOES NOT (deliberately, left as a manual follow-up):
- Set a password for `app_runtime` — a password embedded in a migration
  file becomes a permanent plaintext secret in git history, exactly the
  mistake flagged for the n8n workflow (docs/edge-cases.md, 2026-09-11).
  Set it manually, once, via the Supabase SQL editor or `psql`:
      ALTER ROLE app_runtime WITH PASSWORD '<a real generated secret>';
- Switch `DATABASE_URL` to connect as `app_runtime` instead of the current
  (owning) role — until that happens, this migration has zero practical
  effect, by design (see above). Cutting over requires:
    1. Set the password as above.
    2. Update `DATABASE_URL` (in Render's env vars, not committed) to use
       `app_runtime` instead of the current role.
    3. Add a middleware/dependency that runs
       `SET LOCAL app.authenticated = 'true'` on the DB session for every
       request that has already passed `get_current_salesperson` — e.g. in
       `app/core/database.py::get_db`, gated on a request-scoped flag set by
       the auth dependency. Not implemented in this migration since it's an
       application-code change, not a schema change — do it alongside the
       cutover, not before (a code change with no matching cutover is dead
       code; a cutover with no matching code change locks the app out of its
       own data, since `app_runtime` alone can't produce any row without the
       flag ever being set).
    4. Test against a staging/non-live database first — this changes the
       actual authorization boundary at the DB level, unlike everything else
       in this migration, which is inert until this step happens.
- Give `app_runtime` any privilege beyond what's granted here (no DDL
  rights, no ownership) — migrations must continue to run as the current
  owning role, never as `app_runtime`.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c7d8e9f0a1b2'
down_revision: Union[str, Sequence[str], None] = 'a1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

APP_TABLES = [
    "proposals",
    "proposal_sections",
    "intake_submissions",
    "claude_call_logs",
    "document_artifacts",
    "delivery_records",
    "activity_log_entries",
]


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # Local/test fallback (sqlite) has no roles/RLS concept — no-op there.
        return

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_runtime') THEN
                CREATE ROLE app_runtime WITH LOGIN NOCREATEDB NOCREATEROLE NOSUPERUSER;
            END IF;
        END
        $$;
        """
    )

    for table in APP_TABLES:
        # asyncpg's prepared-statement execution rejects multiple SQL
        # commands in one call — every statement is its own op.execute().
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO app_runtime;")
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY;')
        op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY;')
        op.execute(f'DROP POLICY IF EXISTS require_authenticated_session ON "{table}";')
        op.execute(
            f"""CREATE POLICY require_authenticated_session ON "{table}"
                USING (current_setting('app.authenticated', true) = 'true')
                WITH CHECK (current_setting('app.authenticated', true) = 'true');"""
        )

    op.execute("GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO app_runtime;")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    for table in APP_TABLES:
        op.execute(f'DROP POLICY IF EXISTS require_authenticated_session ON "{table}";')
        op.execute(f'ALTER TABLE "{table}" NO FORCE ROW LEVEL SECURITY;')
        op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY;')
        op.execute(f"REVOKE ALL ON {table} FROM app_runtime;")

    op.execute("REVOKE USAGE ON ALL SEQUENCES IN SCHEMA public FROM app_runtime;")
    op.execute("DROP ROLE IF EXISTS app_runtime;")
