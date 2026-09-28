"""Ticket management API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from community_service_desk.api.deps import (
    get_current_membership,
    get_current_organization,
    get_current_user,
)
from community_service_desk.database import get_db
from community_service_desk.models.organization import Organization
from community_service_desk.models.ticket import Ticket
from community_service_desk.models.user import Membership, User
from community_service_desk.schemas.search import TicketSearchFilter
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
from community_service_desk.services.authorization_service import (
    AuthorizationService,
    Roles,
)
from community_service_desk.services.conversation_service import ConversationService
from community_service_desk.services.search_service import SearchService
from community_service_desk.services.ticket_lifecycle import TicketLifecycleService
from community_service_desk.services.ticket_service import TicketService

router = APIRouter(prefix="/tickets", tags=["Tickets"])


@router.post("", response_model=TicketListItem, status_code=status.HTTP_201_CREATED)
def create_ticket(
    data: TicketCreate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    org: Annotated[Organization, Depends(get_current_organization)],
    membership: Annotated[Membership, Depends(get_current_membership)],
):
    """Create a new ticket within the active organization context."""
    is_agent = membership.role in Roles.STAFF_ROLES
    actor_user = user if is_agent else None
    requester_user = user if not is_agent else None

    ticket = TicketService.create_ticket(
        db=db,
        organization_id=org.id,
        data=data,
        actor_user=actor_user,
        requester_user=requester_user,
    )
    return ticket


@router.get("", response_model=list[TicketListItem])
def list_tickets(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    org: Annotated[Organization, Depends(get_current_organization)],
    membership: Annotated[Membership, Depends(get_current_membership)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    priority: Annotated[str | None, Query()] = None,
    queue_id: Annotated[str | None, Query()] = None,
    assigned_agent_id: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """List tickets for the current organization with role-based scoping."""
    is_staff = membership.role in Roles.STAFF_ROLES
    req_uid = None if is_staff else user.id
    req_email = None if is_staff else user.email

    filters = TicketSearchFilter(
        status=status_filter,
        priority=priority,
        queue_id=queue_id,
        assigned_agent_id=assigned_agent_id,
        limit=limit,
        offset=offset,
    )

    tickets = SearchService.search_tickets(
        db=db,
        organization_id=org.id,
        filters=filters,
        requester_user_id=req_uid,
        requester_email=req_email,
    )
    return tickets


@router.get("/stats/dashboard", response_model=DashboardStats)
def get_dashboard_statistics(
    db: Annotated[Session, Depends(get_db)],
    org: Annotated[Organization, Depends(get_current_organization)],
    membership: Annotated[Membership, Depends(get_current_membership)],
):
    """Retrieve ticket counter statistics for the organization dashboard."""
    return TicketService.get_dashboard_stats(db, org.id)


@router.get("/{ticket_id}")
def get_ticket(
    ticket_id: str,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    org: Annotated[Organization, Depends(get_current_organization)],
    membership: Annotated[Membership, Depends(get_current_membership)],
):
    """Fetch ticket details with strict server-side boundary filtering."""
    ticket = (
        db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.organization_id == org.id).first()
    )
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found.",
        )

    # Server-side authorization check
    AuthorizationService.assert_ticket_access(user, ticket)

    is_staff = membership.role in Roles.STAFF_ROLES

    if is_staff:
        # Staff members receive full view including internal notes and audit history
        return TicketRead.model_validate(ticket)
    else:
        # Requesters receive strictly filtered view:
        # 1. Filter out all INTERNAL_NOTE entries
        # 2. Exclude audit history
        visible_conv = ConversationService.get_visible_entries(
            ticket.conversation_entries, user, org.id
        )
        return RequesterTicketRead(
            id=ticket.id,
            organization_id=ticket.organization_id,
            ticket_number=ticket.ticket_number,
            title=ticket.title,
            description=ticket.description,
            status=ticket.status,
            priority=ticket.priority,
            category=ticket.category,
            tags=ticket.tags or [],
            created_at=ticket.created_at,
            updated_at=ticket.updated_at,
            resolved_at=ticket.resolved_at,
            requester=ticket.requester,
            conversation_entries=[e for e in visible_conv],
            resolution=ticket.resolution,
            attachments=ticket.attachments,
        )


@router.patch("/{ticket_id}", response_model=TicketListItem)
def update_ticket(
    ticket_id: str,
    data: TicketUpdate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    org: Annotated[Organization, Depends(get_current_organization)],
):
    """Update ticket properties (staff only)."""
    ticket = (
        db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.organization_id == org.id).first()
    )
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found.")

    AuthorizationService.assert_ticket_modification(user, ticket)
    updated = TicketService.update_properties(db, ticket, data, actor=user)
    return updated


@router.post("/{ticket_id}/status", response_model=TicketListItem)
def change_ticket_status(
    ticket_id: str,
    data: TicketStatusUpdate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    org: Annotated[Organization, Depends(get_current_organization)],
):
    """Transition ticket lifecycle status with validation and history logging."""
    ticket = (
        db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.organization_id == org.id).first()
    )
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found.")

    AuthorizationService.assert_ticket_modification(user, ticket)
    updated = TicketLifecycleService.transition_status(
        db=db,
        ticket=ticket,
        new_status=data.status,
        actor=user,
        reason=data.reason,
    )
    return updated


@router.post("/{ticket_id}/assign", response_model=TicketListItem)
def assign_ticket(
    ticket_id: str,
    data: TicketAssignUpdate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    org: Annotated[Organization, Depends(get_current_organization)],
):
    """Assign or reassign a ticket to a support agent."""
    ticket = (
        db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.organization_id == org.id).first()
    )
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found.")

    AuthorizationService.assert_ticket_modification(user, ticket)
    updated = TicketService.assign_ticket(
        db=db,
        ticket=ticket,
        assigned_agent_id=data.assigned_agent_id,
        actor=user,
    )
    return updated
