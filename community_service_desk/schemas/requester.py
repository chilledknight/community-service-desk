"""Requester schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RequesterCreate(BaseModel):
    email: EmailStr
    name: str = Field(..., min_length=2, max_length=255)
    phone: str | None = Field(None, max_length=50)
    notes: str | None = None


class RequesterUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=255)
    phone: str | None = Field(None, max_length=50)
    notes: str | None = None


class RequesterRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    user_id: str | None = None
    email: str
    name: str
    phone: str | None = None
    notes: str | None = None
    created_at: datetime
