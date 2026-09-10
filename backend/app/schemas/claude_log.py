from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict


class ClaudeCallLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    section_key: str
    call_type: str
    status: str
    instruction: Optional[str] = None
    model: Optional[str] = None
    system_prompt: str
    user_prompt: str
    response_text: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    stop_reason: Optional[str] = None
    duration_ms: Optional[int] = None
    error_message: Optional[str] = None
    created_at: datetime
