"""Queue schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class QueueCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    description: str | None = None
    active: bool = True


class QueueUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=100)
    description: str | None = None
    active: bool | None = None


class QueueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    name: str
    description: str | None = None
    active: bool
    created_at: datetime
    updated_at: datetime
