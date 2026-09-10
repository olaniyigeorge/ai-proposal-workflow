from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict

from app.models.activity_log import ActivityEventType


class ActivityLogEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    proposal_id: UUID
    event_type: ActivityEventType
    description: str
    actor: Optional[str] = None
    event_metadata: dict
    created_at: datetime
