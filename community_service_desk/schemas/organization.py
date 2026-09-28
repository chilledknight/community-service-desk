"""Organization schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class OrganizationCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    slug: str = Field(..., min_length=2, max_length=100, pattern=r"^[a-z0-9-]+$")


class OrganizationUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=255)
    status: str | None = Field(None, pattern=r"^(active|suspended|archived)$")


class OrganizationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    status: str
    created_at: datetime
    updated_at: datetime
