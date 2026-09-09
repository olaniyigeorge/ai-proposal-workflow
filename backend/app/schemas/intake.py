from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class IntakePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timestamp: str = Field(..., description="Google Form submission timestamp (for idempotency)")
    respondent_email: EmailStr = Field(..., description="Form submitter email address (for idempotency)")
    client_name: str = Field(..., min_length=1, description="Name of the client")
    client_email: EmailStr = Field(..., description="Client delivery email address")
    company_name: str = Field(..., min_length=1, description="Company/Client organisation")
    date_of_call: str = Field(..., min_length=1, description="Date of discovery call")
    salesperson_name: str = Field(..., min_length=1, description="Salesperson handling the engagement")
    client_needs_summary: str = Field(..., min_length=1, description="Summary of client's needs")
    project_scope: str = Field(..., min_length=1, description="Project scope details")
    goals_and_objectives: str = Field(..., min_length=1, description="Goals and objectives")
    recommended_services: str = Field(..., min_length=1, description="Recommended services or deliverables")
    proposed_timeline: str = Field(..., min_length=1, description="Proposed timeline")
    estimated_pricing: str = Field(..., min_length=1, description="Estimated pricing")


class IntakeResponse(BaseModel):
    success: bool = True
    message: str
    proposal_id: UUID
    status: Literal["created", "existing"]
