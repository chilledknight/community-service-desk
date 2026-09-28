"""Ticket schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from community_service_desk.schemas.attachment import AttachmentRead
from community_service_desk.schemas.conversation import ConversationRead, RequesterConversationRead
from community_service_desk.schemas.event_history import EventHistoryRead
from community_service_desk.schemas.queue import QueueRead
from community_service_desk.schemas.requester import RequesterRead
from community_service_desk.schemas.resolution import ResolutionRead
from community_service_desk.schemas.user import UserRead


class TicketCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=255)
    description: str = Field(..., min_length=5)
    priority: str = Field(default="NORMAL", pattern=r"^(LOW|NORMAL|HIGH|URGENT)$")
    category: str | None = Field(None, max_length=100)
    tags: list[str] = Field(default_factory=list)
    queue_id: str | None = None

    # Requester info (required if anonymous/agent creating for someone, or inferred from current user)
    requester_email: EmailStr | None = None
    requester_name: str | None = None


class TicketUpdate(BaseModel):
    title: str | None = Field(None, min_length=3, max_length=255)
    description: str | None = Field(None, min_length=5)
    priority: str | None = Field(None, pattern=r"^(LOW|NORMAL|HIGH|URGENT)$")
    category: str | None = Field(None, max_length=100)
    tags: list[str] | None = None
    queue_id: str | None = None


class TicketStatusUpdate(BaseModel):
    status: str = Field(
        ...,
        pattern=r"^(NEW|OPEN|IN_PROGRESS|WAITING_ON_REQUESTER|WAITING_INTERNAL|RESOLVED|CLOSED)$",
    )
    reason: str | None = None


class TicketAssignUpdate(BaseModel):
    assigned_agent_id: str | None = None  # None indicates unassigning


class TicketListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    ticket_number: str
    title: str
    status: str
    priority: str
    category: str | None = None
    tags: list[str] = []
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None = None
    requester: RequesterRead
    queue: QueueRead | None = None
    assigned_agent: UserRead | None = None


class TicketRead(BaseModel):
    """Full ticket detail schema for authorized agents and administrators."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    ticket_number: str
    title: str
    description: str
    status: str
    priority: str
    category: str | None = None
    tags: list[str] = []
    queue_id: str | None = None
    assigned_agent_id: str | None = None

    created_at: datetime
    updated_at: datetime
    first_response_at: datetime | None = None
    resolved_at: datetime | None = None
    closed_at: datetime | None = None
    reopened_at: datetime | None = None

    requester: RequesterRead
    queue: QueueRead | None = None
    assigned_agent: UserRead | None = None

    conversation_entries: list[ConversationRead] = []
    history_entries: list[EventHistoryRead] = []
    resolution: ResolutionRead | None = None
    attachments: list[AttachmentRead] = []


class RequesterTicketRead(BaseModel):
    """Restricted ticket detail schema for requesters. No internal notes or private audit trails."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    ticket_number: str
    title: str
    description: str
    status: str
    priority: str
    category: str | None = None
    tags: list[str] = []

    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None = None

    requester: RequesterRead
    conversation_entries: list[RequesterConversationRead] = []
    resolution: ResolutionRead | None = None
    attachments: list[AttachmentRead] = []


class DashboardStats(BaseModel):
    new_count: int = 0
    open_count: int = 0
    in_progress_count: int = 0
    waiting_count: int = 0
    unassigned_count: int = 0
    resolved_recently_count: int = 0
    total_tickets: int = 0
