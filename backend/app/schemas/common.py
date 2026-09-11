from typing import Generic, Optional, TypeVar
from pydantic import BaseModel

DataT = TypeVar("DataT")


class HealthResponse(BaseModel):
    status: str
    environment: str
    version: str = "0.1.0"


class SalespersonProfileResponse(BaseModel):
    user_id: str
    email: str
    role: str = "salesperson"
    display_name: Optional[str] = None


class ApiResponse(BaseModel, Generic[DataT]):
    success: bool = True
    data: Optional[DataT] = None
    message: Optional[str] = None
