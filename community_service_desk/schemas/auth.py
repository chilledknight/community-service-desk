"""Authentication schemas."""

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1)
    organization_slug: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    display_name: str
    organization_id: str | None = None
    role: str | None = None


class UserProfile(BaseModel):
    id: str
    email: str
    display_name: str
    active: bool
    roles_by_org: dict[str, str] = {}
