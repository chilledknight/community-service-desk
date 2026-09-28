"""Structured resolution schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ResolutionCreate(BaseModel):
    summary: str = Field(
        ..., min_length=5, description="Concise explanation of what fixed the issue"
    )
    root_cause: str | None = Field(None, description="Underlying cause of the problem")
    resolution_steps: str = Field(..., min_length=5, description="What steps were taken to resolve")
    verification: str = Field(
        default="admin_verified",
        description="How resolution was confirmed (e.g. requester confirmed, automated test passed, administrator verified)",
    )
    knowledge_useful: bool = Field(
        default=False,
        description="Indicates whether this resolution is potentially useful for future similar tickets",
    )


class ResolutionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    ticket_id: str
    organization_id: str
    resolved_by_id: str
    summary: str
    root_cause: str | None = None
    resolution_steps: str
    verification: str
    knowledge_useful: bool
    created_at: datetime
    updated_at: datetime
