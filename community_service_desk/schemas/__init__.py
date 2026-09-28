"""Community Service Desk Schemas."""

from community_service_desk.schemas.attachment import AttachmentRead
from community_service_desk.schemas.auth import LoginRequest, TokenResponse, UserProfile
from community_service_desk.schemas.conversation import (
    ConversationCreate,
    ConversationRead,
    RequesterConversationRead,
)
from community_service_desk.schemas.event_history import EventHistoryRead
from community_service_desk.schemas.organization import (
    OrganizationCreate,
    OrganizationRead,
    OrganizationUpdate,
)
from community_service_desk.schemas.queue import (
    QueueCreate,
    QueueRead,
    QueueUpdate,
)
from community_service_desk.schemas.requester import (
    RequesterCreate,
    RequesterRead,
    RequesterUpdate,
)
from community_service_desk.schemas.resolution import (
    ResolutionCreate,
    ResolutionRead,
)
from community_service_desk.schemas.search import (
    KnowledgeEvidence,
    KnowledgeSearchQuery,
    TicketSearchFilter,
)
from community_service_desk.schemas.ticket import (
    DashboardStats,
    RequesterTicketRead,
    TicketAssignUpdate,
    TicketCreate,
    TicketListItem,
    TicketRead,
    TicketStatusUpdate,
    TicketUpdate,
)
from community_service_desk.schemas.user import (
    MembershipRead,
    UserCreate,
    UserRead,
    UserUpdate,
)

__all__ = [
    "LoginRequest",
    "TokenResponse",
    "UserProfile",
    "OrganizationCreate",
    "OrganizationUpdate",
    "OrganizationRead",
    "UserCreate",
    "UserUpdate",
    "UserRead",
    "MembershipRead",
    "RequesterCreate",
    "RequesterUpdate",
    "RequesterRead",
    "QueueCreate",
    "QueueUpdate",
    "QueueRead",
    "ConversationCreate",
    "ConversationRead",
    "RequesterConversationRead",
    "EventHistoryRead",
    "ResolutionCreate",
    "ResolutionRead",
    "AttachmentRead",
    "TicketCreate",
    "TicketUpdate",
    "TicketStatusUpdate",
    "TicketAssignUpdate",
    "TicketListItem",
    "TicketRead",
    "RequesterTicketRead",
    "DashboardStats",
    "TicketSearchFilter",
    "KnowledgeSearchQuery",
    "KnowledgeEvidence",
]
