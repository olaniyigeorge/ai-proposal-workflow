"""Manually approve a salesperson account directly against the DB.

Exists to solve the bootstrap problem: `POST /auth/pending/{id}/approve`
requires an already-approved salesperson to call it, so the very first
account can't be approved through the API at all — nobody has that
privilege yet. Run this once per new deployment (or whenever the "any
approved salesperson can approve the next" chain needs a manual nudge, e.g.
every existing approved account left the company):

    python -m scripts.approve_salesperson --email newperson@company.com

Requires the account to already exist as PENDING (i.e. that person has
signed up and made at least one authenticated request — get_or_create_pending
in app/core/security.py creates the row on first sight). If they haven't
signed up yet, there's nothing here to approve.
"""

import argparse
import asyncio

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.salesperson_account import SalespersonAccount, SalespersonAccountStatus


async def approve_by_email(email: str) -> None:
    async with AsyncSessionLocal() as db:
        stmt = select(SalespersonAccount).where(SalespersonAccount.email == email)
        account = (await db.execute(stmt)).scalar_one_or_none()
        if account is None:
            print(
                f"No account found for {email} — they need to sign up (or make one "
                "authenticated request) first so their pending row exists."
            )
            return

        previous_status = account.status.value
        account.status = SalespersonAccountStatus.APPROVED
        account.approved_by = "bootstrap-script"
        await db.commit()
        print(f"Approved {email} (was {previous_status}).")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True, help="Email of the account to approve")
    args = parser.parse_args()
    asyncio.run(approve_by_email(args.email))


if __name__ == "__main__":
    main()
