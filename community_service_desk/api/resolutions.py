"""Ticket structured resolution API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from community_service_desk.api.deps import (
    get_current_organization,
    get_current_user,
)
from community_service_desk.database import get_db
from community_service_desk.models.organization import Organization
from community_service_desk.models.resolution import TicketResolution
from community_service_desk.models.ticket import Ticket
from community_service_desk.models.user import User
from community_service_desk.schemas.resolution import ResolutionCreate, ResolutionRead
from community_service_desk.services.authorization_service import AuthorizationService
from community_service_desk.services.resolution_service import ResolutionService

router = APIRouter(prefix="/tickets/{ticket_id}/resolution", tags=["Resolutions"])


@router.post("", response_model=ResolutionRead, status_code=status.HTTP_201_CREATED)
def record_ticket_resolution(
    ticket_id: str,
    data: ResolutionCreate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    org: Annotated[Organization, Depends(get_current_organization)],
):
    """Record a structured resolution on a ticket (staff only)."""
    ticket = (
        db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.organization_id == org.id).first()
    )
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found.")

    AuthorizationService.assert_ticket_modification(user, ticket)
    resolution = ResolutionService.record_resolution(
        db=db,
        ticket=ticket,
        data=data,
        actor=user,
    )
    return resolution


@router.get("", response_model=ResolutionRead)
def get_ticket_resolution(
    ticket_id: str,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    org: Annotated[Organization, Depends(get_current_organization)],
):
    """Retrieve structured resolution for a ticket."""
    ticket = (
        db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.organization_id == org.id).first()
    )
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found.")

    AuthorizationService.assert_ticket_access(user, ticket)

    resolution = db.query(TicketResolution).filter(TicketResolution.ticket_id == ticket.id).first()
    if not resolution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No resolution recorded for this ticket.",
        )
    return resolution
