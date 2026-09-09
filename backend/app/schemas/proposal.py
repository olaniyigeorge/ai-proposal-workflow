from datetime import datetime
from typing import List
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr


class ProposalSectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    section_key: str
    title: str
    order_index: int
    content: str
    content_origin: str
    approval_status: str
    regeneration_count: int
    version: int
    created_at: datetime
    updated_at: datetime


class ProposalSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    client_name: str
    client_email: EmailStr
    company_name: str
    salesperson_name: str
    created_at: datetime
    updated_at: datetime


class ProposalDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    client_name: str
    client_email: EmailStr
    company_name: str
    salesperson_name: str
    date_of_call: str
    client_needs_summary: str
    project_scope: str
    goals_and_objectives: str
    recommended_services: str
    proposed_timeline: str
    estimated_pricing: str
    created_at: datetime
    updated_at: datetime
    sections: List[ProposalSectionResponse]
