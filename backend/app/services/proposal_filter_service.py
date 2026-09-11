"""
Proposal list filtering + pagination + KPI computation (week-3 feature).

The existing GET /proposals endpoint was a single unfiltered scan; this adds
server-side filters on status / salesperson_name / date range / company / client
name with offset pagination, plus a separate analytics endpoint that computes
KPIs from proposals + delivery_records + client_response_records.

KPIs are computed on demand (not pre-aggregated) — correct for the current
mid-scale volume and avoids a background aggregation pipeline.
"""

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client_feedback import ClientResponseRecord, ClientResponseType
from app.models.delivery import DeliveryRecord, DeliveryStatus
from app.models.proposal import Proposal, ProposalStatus
from app.schemas.extended import KpiSummaryResponse, ProposalFilterParams


def _filter_where(params: ProposalFilterParams):
    """Return a list of SQLAlchemy WHERE clauses for the given filter params."""
    clauses: list = []
    if params.status:
        clauses.append(Proposal.status == params.status)
    if params.salesperson_name:
        clauses.append(Proposal.salesperson_name.ilike(f"%{params.salesperson_name}%"))
    if params.date_from:
        clauses.append(Proposal.created_at >= params.date_from)
    if params.date_to:
        clauses.append(Proposal.created_at <= params.date_to)
    if params.company_name:
        clauses.append(Proposal.company_name.ilike(f"%{params.company_name}%"))
    if params.client_name:
        clauses.append(Proposal.client_name.ilike(f"%{params.client_name}%"))
    return clauses


async def list_proposals_filtered(
    db: AsyncSession, params: ProposalFilterParams
) -> tuple[list[Proposal], int]:
    """Return (proposals, total_count) for the given filter + pagination."""
    base = select(Proposal)
    for clause in _filter_where(params):
        base = base.where(clause)

    count_stmt = select(func.count()).select_from(base.subquery())
    data_stmt = (
        base.order_by(Proposal.created_at.desc())
        .offset(params.skip)
        .limit(params.limit)
    )

    count_result = await db.execute(count_stmt)
    total = int(count_result.scalar_one())

    result = await db.execute(data_stmt)
    proposals = list(result.scalars().all())
    return proposals, total


async def compute_kpis(
    db: AsyncSession,
    *,
    period_from: Optional[datetime] = None,
    period_to: Optional[datetime] = None,
) -> KpiSummaryResponse:
    """Compute KPIs from proposals + delivery_records + client_response_records.

    period_from / period_to restrict everything to a date window; when omitted
    the KPIs cover all proposals in the database.
    """
    window_on_proposal = []
    if period_from:
        window_on_proposal.append(Proposal.created_at >= period_from)
    if period_to:
        window_on_proposal.append(Proposal.created_at <= period_to)
    window_clause = and_(*window_on_proposal) if window_on_proposal else None

    # Helper: count query against Proposal with optional window + optional extra join/filter
    async def count_proposals(extra_where=None):
        stmt = select(func.count(Proposal.id))
        if window_clause is not None:
            stmt = stmt.where(window_clause)
        if extra_where is not None:
            stmt = stmt.where(extra_where)
        res = await db.execute(stmt)
        return int(res.scalar_one())

    # delivered = proposals with a SENT delivery record (counted at delivery-record level,
    # one row per delivery; if a proposal was delivered multiple times we still count it once
    # for KPI purposes — count distinct proposal_ids)
    delivered_stmt = (
        select(func.count())
        .select_from(
            select(DeliveryRecord.proposal_id)
            .where(DeliveryRecord.status == DeliveryStatus.SENT)
            .where(Proposal.id == DeliveryRecord.proposal_id)
            .where(window_clause) if window_clause else select(DeliveryRecord.proposal_id).where(DeliveryRecord.status == DeliveryStatus.SENT).where(Proposal.id == DeliveryRecord.proposal_id)
            .distinct()
            .subquery()
        )
    )
    total_delivered = int((await db.execute(delivered_stmt)).scalar_one())

    # accepted / declined / no_response — count client_response_records whose proposal is in window
    async def count_responses(response_type: ClientResponseType) -> int:
        base = (
            select(func.count(ClientResponseRecord.id))
            .join(Proposal, ClientResponseRecord.proposal_id == Proposal.id)
        )
        base = base.where(ClientResponseRecord.response_type == response_type)
        if window_clause is not None:
            base = base.where(window_clause)
        res = await db.execute(base)
        return int(res.scalar_one())

    total_accepted = await count_responses(ClientResponseType.ACCEPTED)
    total_declined = await count_responses(ClientResponseType.DECLINED)
    total_no_response = await count_responses(ClientResponseType.NO_RESPONSE)

    total_proposals = await count_proposals()

    respondent_total = total_accepted + total_declined + total_no_response

    def pct(part: int, whole: int) -> Optional[float]:
        return round(100.0 * part / whole, 2) if whole else None

    accepted_rate = pct(total_accepted, respondent_total)
    declined_rate = pct(total_declined, respondent_total)
    no_response_rate = pct(total_no_response, respondent_total)

    won_proposals = total_accepted
    won_rate = pct(won_proposals, total_delivered) if total_delivered else None

    # proposals by status
    by_status_stmt = select(Proposal.status, func.count(Proposal.id)).group_by(Proposal.status)
    if window_clause is not None:
        by_status_stmt = by_status_stmt.where(window_clause)
    status_rows = await db.execute(by_status_stmt)
    proposals_by_status: dict[str, int] = {}
    for status_val, cnt in status_rows.fetchall():
        proposals_by_status[str(status_val)] = int(cnt)

    # proposals by salesperson
    by_sp_stmt = select(Proposal.salesperson_name, func.count(Proposal.id)).group_by(Proposal.salesperson_name)
    if window_clause is not None:
        by_sp_stmt = by_sp_stmt.where(window_clause)
    sp_rows = await db.execute(by_sp_stmt)
    proposals_by_salesperson: dict[str, int] = {}
    for name_val, cnt in sp_rows.fetchall():
        proposals_by_salesperson[name_val or "(unassigned)"] = int(cnt)

    # average time from created_at to first SENT delivery, in hours
    avg_hours: Optional[float] = None
    if total_delivered:
        avg_stmt = (
            select(
                func.avg(
                    func.extract(
                        "epoch",
                        DeliveryRecord.sent_at - Proposal.created_at,
                    )
                )
            )
            .join(Proposal, DeliveryRecord.proposal_id == Proposal.id)
            .where(DeliveryRecord.status == DeliveryStatus.SENT)
        )
        if window_clause is not None:
            avg_stmt = avg_stmt.where(window_clause)
        raw = (await db.execute(avg_stmt)).scalar_one()
        if raw is not None:
            try:
                avg_hours = round(float(raw) / 3600.0, 2)
            except (TypeError, ValueError):
                avg_hours = None

    return KpiSummaryResponse(
        total_proposals=total_proposals,
        total_delivered=total_delivered,
        total_accepted=total_accepted,
        total_declined=total_declined,
        total_no_response=total_no_response,
        accepted_rate_pct=accepted_rate,
        declined_rate_pct=declined_rate,
        no_response_rate_pct=no_response_rate,
        won_proposals=won_proposals,
        won_rate_pct=won_rate,
        average_time_to_delivery_hours=avg_hours,
        proposals_by_status=proposals_by_status,
        proposals_by_salesperson=proposals_by_salesperson,
        period_from=period_from,
        period_to=period_to,
    )
