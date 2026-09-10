from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict


class DeliveryDraftResponse(BaseModel):
    subject: str
    body: str
    recipient_email: str


class DeliveryRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    recipient_email: str
    subject: str
    sent_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime
