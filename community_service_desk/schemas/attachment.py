"""Attachment schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AttachmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    ticket_id: str
    filename: str
    content_type: str
    size: int
    created_at: datetime
    uploaded_by_id: str | None = None
