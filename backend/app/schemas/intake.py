from typing import Literal, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class IntakePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timestamp: str = Field(..., description="Google Form submission timestamp (for idempotency)")
    respondent_email: EmailStr = Field(..., description="Form submitter email address (for idempotency)")
    client_name: str = Field(..., min_length=1, description="Name of the client")
    client_email: EmailStr = Field(..., description="Client delivery email address")
    company_name: str = Field(..., min_length=1, description="Company/Client organisation")
    date_of_call: str = Field(..., min_length=1, description="Date of discovery call")
    # Optional: the client can fill this form directly with no salesperson on
    # the call at all (docs/decisions.md #20). Left blank, the proposal is
    # unassigned and picked up via a manual claim/assign step rather than
    # guessed at from free text. See docs/edge-cases.md "Salesperson
    # attribution breaks when the client fills the form".
    salesperson_name: Optional[str] = Field(
        None, description="Salesperson handling the engagement, if one was involved"
    )
    client_needs_summary: str = Field(..., min_length=1, description="Summary of client's needs")
    project_scope: str = Field(..., min_length=1, description="Project scope details")
    goals_and_objectives: str = Field(..., min_length=1, description="Goals and objectives")
    recommended_services: str = Field(..., min_length=1, description="Recommended services or deliverables")
    proposed_timeline: str = Field(..., min_length=1, description="Proposed timeline")
    estimated_pricing: str = Field(..., min_length=1, description="Estimated pricing")

    @field_validator("salesperson_name")
    @classmethod
    def blank_salesperson_name_is_unassigned(cls, value: Optional[str]) -> Optional[str]:
        """A blank/whitespace-only Sheet cell (the client filled the form with
        no salesperson on the call) must mean "unassigned", not the literal
        string "" — normalize it to None so downstream code has one signal
        for "no salesperson attributed" instead of two.
        """
        if value is None or not value.strip():
            return None
        return value


class IntakeResponse(BaseModel):
    success: bool = True
    message: str
    proposal_id: UUID
    status: Literal["created", "existing"]
