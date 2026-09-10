from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict


class DocumentArtifactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    file_size_bytes: int
    page_count: int
    created_at: datetime
    download_url: str
