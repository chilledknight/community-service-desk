"""Ticket conversations API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
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
from community_service_desk.schemas.conversation import (
    ConversationCreate,
    ConversationRead,
    RequesterConversationRead,
)
from community_service_desk.services.authorization_service import (
    AuthorizationService,
    Roles,
)
from community_service_desk.services.conversation_service import ConversationService

router = APIRouter(prefix="/tickets/{ticket_id}/conversations", tags=["Conversations"])


@router.post("", status_code=status.HTTP_201_CREATED)
def add_conversation_entry(
    ticket_id: str,
    data: ConversationCreate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    org: Annotated[Organization, Depends(get_current_organization)],
    membership: Annotated[Membership, Depends(get_current_membership)],
):
    """Add a public reply or internal note to a ticket."""
    ticket = (
        db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.organization_id == org.id).first()
    )
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found.")

    AuthorizationService.assert_ticket_access(user, ticket)

    entry = ConversationService.add_entry(
        db=db,
        ticket=ticket,
        body=data.body,
        entry_type=data.entry_type,
        actor=user,
        actor_role=membership.role,
    )

    if membership.role in Roles.STAFF_ROLES:
        return ConversationRead.model_validate(entry)
    else:
        return RequesterConversationRead.model_validate(entry)


@router.get("")
def list_conversation_entries(
    ticket_id: str,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    org: Annotated[Organization, Depends(get_current_organization)],
    membership: Annotated[Membership, Depends(get_current_membership)],
):
    """Retrieve conversation entries with strict server-side note privacy filtering."""
    ticket = (
        db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.organization_id == org.id).first()
    )
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found.")

    AuthorizationService.assert_ticket_access(user, ticket)

    visible_entries = ConversationService.get_visible_entries(
        ticket.conversation_entries, user, org.id
    )

    if membership.role in Roles.STAFF_ROLES:
        return [ConversationRead.model_validate(e) for e in visible_entries]
    else:
        return [RequesterConversationRead.model_validate(e) for e in visible_entries]
