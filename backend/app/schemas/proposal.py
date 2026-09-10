from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RegenerationLogEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    instruction: str
    attempted_at: str
    outcome: str
    resulting_version: Optional[int] = None
    error: Optional[str] = None


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
    regeneration_log: List[RegenerationLogEntry] = []
    created_at: datetime
    updated_at: datetime


class SectionUpdateRequest(BaseModel):
    content: str = Field(..., min_length=1)

    @field_validator("content")
    @classmethod
    def content_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("content cannot be blank")
        return value


class SectionRegenerateRequest(BaseModel):
    instruction: str = Field(..., min_length=1)

    @field_validator("instruction")
    @classmethod
    def instruction_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("instruction cannot be blank")
        return value


class RequestChangesRequest(BaseModel):
    reason: Optional[str] = None


class RejectProposalRequest(BaseModel):
    reason: Optional[str] = None


class ProposalSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    client_name: str
    client_email: EmailStr
    company_name: str
    salesperson_name: Optional[str]
    created_at: datetime
    updated_at: datetime


class ProposalDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    client_name: str
    client_email: EmailStr
    company_name: str
    salesperson_name: Optional[str]
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
