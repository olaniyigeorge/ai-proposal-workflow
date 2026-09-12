from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

from app.models.client_feedback import ClientResponseType, FeedbackCategory


class ClientResponseRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    proposal_id: UUID
    response_type: ClientResponseType
    feedback_text: Optional[str] = None
    client_ip: Optional[str] = None
    created_at: datetime


class ClientPageMetaResponse(BaseModel):
    """What the public client page needs to render — proposal identity + whether
    the document is ready, without exposing salesperson or internal state."""
    model_config = ConfigDict(from_attributes=True)

    proposal_id: UUID
    client_name: str
    company_name: str
    document_ready: bool
    document_download_url: Optional[str] = None


class FeedbackEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    category: FeedbackCategory
    text: str
    actor_email: str
    created_at: datetime


class ProposalFilterParams(BaseModel):
    """Queryable filter shape for GET /proposals."""
    status: Optional[str] = None
    salesperson_name: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    company_name: Optional[str] = None
    client_name: Optional[str] = None
    skip: int = 0
    limit: int = 50


class KpiSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_proposals: int
    total_delivered: int
    total_accepted: int
    total_declined: int
    total_no_response: int
    accepted_rate_pct: Optional[float] = None
    declined_rate_pct: Optional[float] = None
    no_response_rate_pct: Optional[float] = None
    won_proposals: int
    won_rate_pct: Optional[float] = None
    average_time_to_delivery_hours: Optional[float] = None
    proposals_by_status: dict[str, int]
    proposals_by_salesperson: dict[str, int]
    period_from: Optional[datetime] = None
    period_to: Optional[datetime] = None


class ClientResponseRequest(BaseModel):
    """Payload the public client page POSTs when the recipient clicks Accept or Decline."""
    response_type: ClientResponseType
    feedback_text: Optional[str] = Field(default=None, max_length=2000)

    model_config = ConfigDict(extra="forbid")


class FeedbackEntryRequest(BaseModel):
    category: FeedbackCategory
    text: str = Field(..., min_length=1, max_length=4000)

    model_config = ConfigDict(extra="forbid")