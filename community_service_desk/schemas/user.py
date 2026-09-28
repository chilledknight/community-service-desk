"""User and membership schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    display_name: str = Field(..., min_length=2, max_length=255)
    password: str = Field(..., min_length=8)
    role: str = Field(default="agent", pattern=r"^(organization_admin|agent|requester)$")


class UserUpdate(BaseModel):
    display_name: str | None = Field(None, min_length=2, max_length=255)
    active: bool | None = None
    role: str | None = Field(None, pattern=r"^(organization_admin|agent|requester)$")


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    display_name: str
    active: bool
    created_at: datetime
    last_login_at: datetime | None = None


class MembershipRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    user_id: str
    role: str
    created_at: datetime
    user: UserRead | None = None
