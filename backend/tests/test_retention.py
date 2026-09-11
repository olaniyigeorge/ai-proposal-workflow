"""Tests for scripts/enforce_retention.py — docs/reference/data-retention-policy.md's
retention windows (proposals 24mo, activity logs 12mo). Not run automatically
inside the API; this is a scheduled job, tested directly against its
delete-count and dry-run behavior.
"""

from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio

import scripts.enforce_retention as enforce_retention
from app.models.activity_log import ActivityEventType, ActivityLogEntry
from app.models.proposal import (
    ContentOrigin,
    Proposal,
    ProposalSection,
    ProposalStatus,
    SectionApprovalStatus,
    SectionKey,
)
from tests.conftest import TestAsyncSessionLocal


def _make_proposal(updated_at: datetime) -> Proposal:
    proposal = Proposal(
        status=ProposalStatus.DELIVERED,
        client_name="Alice",
        client_email="alice@acme.com",
        company_name="Acme Corp",
        salesperson_name="Bob",
        date_of_call="2024-01-01",
        client_needs_summary="needs",
        project_scope="scope",
        goals_and_objectives="goals",
        recommended_services="services",
        proposed_timeline="timeline",
        estimated_pricing="$1,000",
    )
    proposal.sections = [
        ProposalSection(
            section_key=SectionKey.INTRODUCTION,
            title="Introduction",
            order_index=0,
            content="x",
            content_origin=ContentOrigin.AI_GENERATED,
            approval_status=SectionApprovalStatus.APPROVED,
            regeneration_count=0,
            version=1,
        )
    ]
    proposal.updated_at = updated_at
    return proposal


@pytest_asyncio.fixture
async def db_session():
    async with TestAsyncSessionLocal() as session:
        yield session


async def _persist(db, proposal: Proposal) -> Proposal:
    db.add(proposal)
    await db.flush()
    await db.commit()
    return proposal


@pytest.mark.asyncio
async def test_dry_run_reports_without_deleting(db_session, monkeypatch) -> None:
    monkeypatch.setattr(enforce_retention, "AsyncSessionLocal", TestAsyncSessionLocal)

    stale_cutoff = datetime.now(timezone.utc) - timedelta(days=800)  # ~26 months
    proposal = await _persist(db_session, _make_proposal(stale_cutoff))
    proposal_id = proposal.id

    await enforce_retention.run(dry_run=True)

    async with TestAsyncSessionLocal() as check_db:
        from app.services.proposal_service import get_proposal_by_id

        still_there = await get_proposal_by_id(check_db, proposal_id)
        assert still_there is not None


@pytest.mark.asyncio
async def test_deletes_proposals_past_retention_window(db_session, monkeypatch) -> None:
    monkeypatch.setattr(enforce_retention, "AsyncSessionLocal", TestAsyncSessionLocal)

    stale_cutoff = datetime.now(timezone.utc) - timedelta(days=800)  # ~26 months
    recent = datetime.now(timezone.utc) - timedelta(days=10)

    stale_proposal = await _persist(db_session, _make_proposal(stale_cutoff))
    fresh_proposal = await _persist(db_session, _make_proposal(recent))
    stale_id, fresh_id = stale_proposal.id, fresh_proposal.id

    await enforce_retention.run(dry_run=False)

    async with TestAsyncSessionLocal() as check_db:
        from app.services.proposal_service import get_proposal_by_id

        assert await get_proposal_by_id(check_db, stale_id) is None
        assert await get_proposal_by_id(check_db, fresh_id) is not None


@pytest.mark.asyncio
async def test_recent_activity_log_entry_keeps_a_stale_updated_at_proposal_alive(
    db_session, monkeypatch
) -> None:
    """updated_at alone would wrongly mark this as stale — a recent
    ActivityLogEntry (e.g. a section edit that didn't touch the Proposal row
    itself) is what should actually count as "last meaningful activity"."""
    monkeypatch.setattr(enforce_retention, "AsyncSessionLocal", TestAsyncSessionLocal)

    stale_updated_at = datetime.now(timezone.utc) - timedelta(days=800)
    proposal = await _persist(db_session, _make_proposal(stale_updated_at))
    db_session.add(
        ActivityLogEntry(
            proposal_id=proposal.id,
            event_type=ActivityEventType.SECTION_EDITED,
            description="recent edit",
        )
    )
    await db_session.commit()
    proposal_id = proposal.id

    await enforce_retention.run(dry_run=False)

    async with TestAsyncSessionLocal() as check_db:
        from app.services.proposal_service import get_proposal_by_id

        assert await get_proposal_by_id(check_db, proposal_id) is not None


@pytest.mark.asyncio
async def test_deletes_activity_log_entries_past_their_own_shorter_window(
    db_session, monkeypatch
) -> None:
    monkeypatch.setattr(enforce_retention, "AsyncSessionLocal", TestAsyncSessionLocal)

    recent = datetime.now(timezone.utc) - timedelta(days=10)
    proposal = await _persist(db_session, _make_proposal(recent))

    old_entry = ActivityLogEntry(
        proposal_id=proposal.id,
        event_type=ActivityEventType.CREATED,
        description="old entry",
    )
    db_session.add(old_entry)
    await db_session.commit()
    old_entry.created_at = datetime.now(timezone.utc) - timedelta(days=400)  # ~13 months
    await db_session.commit()
    old_entry_id = old_entry.id

    await enforce_retention.run(dry_run=False)

    async with TestAsyncSessionLocal() as check_db:
        from sqlalchemy import select

        result = await check_db.execute(
            select(ActivityLogEntry).where(ActivityLogEntry.id == old_entry_id)
        )
        assert result.scalar_one_or_none() is None
