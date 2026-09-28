"""Conversation entry schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from community_service_desk.models.conversation import EntryType


class ConversationCreate(BaseModel):
    body: str = Field(..., min_length=1)
    entry_type: str = Field(
        default=EntryType.REQUESTER_VISIBLE_REPLY,
        pattern=r"^(REQUESTER_VISIBLE_REPLY|INTERNAL_NOTE)$",
    )


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    ticket_id: str
    author_id: str | None = None
    author_name: str
    author_type: str
    entry_type: str
    body: str
    created_at: datetime


class RequesterConversationRead(BaseModel):
    """Safe conversation entry schema for requesters. Never contains internal notes."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    ticket_id: str
    author_name: str
    author_type: str
    entry_type: str = EntryType.REQUESTER_VISIBLE_REPLY
    body: str
    created_at: datetime
