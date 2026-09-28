"""Ticket Lifecycle state machine and status transition management."""

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from community_service_desk.models.event_history import EventType, TicketEventHistory
from community_service_desk.models.ticket import Ticket
from community_service_desk.models.user import User


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TicketStatus:
    NEW = "NEW"
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    WAITING_ON_REQUESTER = "WAITING_ON_REQUESTER"
    WAITING_INTERNAL = "WAITING_INTERNAL"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"

    ALL = {
        NEW,
        OPEN,
        IN_PROGRESS,
        WAITING_ON_REQUESTER,
        WAITING_INTERNAL,
        RESOLVED,
        CLOSED,
    }


class TicketPriority:
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"

    ALL = {LOW, NORMAL, HIGH, URGENT}


# Explicit valid state transitions
VALID_TRANSITIONS: dict[str, set[str]] = {
    TicketStatus.NEW: {
        TicketStatus.OPEN,
        TicketStatus.IN_PROGRESS,
        TicketStatus.RESOLVED,
        TicketStatus.CLOSED,
    },
    TicketStatus.OPEN: {
        TicketStatus.IN_PROGRESS,
        TicketStatus.WAITING_ON_REQUESTER,
        TicketStatus.WAITING_INTERNAL,
        TicketStatus.RESOLVED,
        TicketStatus.CLOSED,
    },
    TicketStatus.IN_PROGRESS: {
        TicketStatus.OPEN,
        TicketStatus.WAITING_ON_REQUESTER,
        TicketStatus.WAITING_INTERNAL,
        TicketStatus.RESOLVED,
        TicketStatus.CLOSED,
    },
    TicketStatus.WAITING_ON_REQUESTER: {
        TicketStatus.IN_PROGRESS,
        TicketStatus.OPEN,
        TicketStatus.RESOLVED,
        TicketStatus.CLOSED,
    },
    TicketStatus.WAITING_INTERNAL: {
        TicketStatus.IN_PROGRESS,
        TicketStatus.OPEN,
        TicketStatus.RESOLVED,
        TicketStatus.CLOSED,
    },
    TicketStatus.RESOLVED: {
        TicketStatus.CLOSED,
        TicketStatus.OPEN,  # Reopen
        TicketStatus.IN_PROGRESS,  # Reopen directly to in-progress
    },
    TicketStatus.CLOSED: {
        TicketStatus.OPEN,  # Reopen
    },
}


class TicketLifecycleService:
    """Manages ticket status transitions and associated event history."""

    @classmethod
    def can_transition(cls, current_status: str, next_status: str) -> bool:
        if current_status == next_status:
            return True
        allowed = VALID_TRANSITIONS.get(current_status, set())
        return next_status in allowed

    @classmethod
    def transition_status(
        cls,
        db: Session,
        ticket: Ticket,
        new_status: str,
        actor: User,
        reason: str | None = None,
    ) -> Ticket:
        """Perform a status transition with validation and audit trail."""
        new_status = new_status.upper()
        if new_status not in TicketStatus.ALL:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid ticket status: '{new_status}'",
            )

        if ticket.status == new_status:
            return ticket

        if not cls.can_transition(ticket.status, new_status):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status transition from '{ticket.status}' to '{new_status}'.",
            )

        old_status = ticket.status
        ticket.status = new_status
        now = utc_now()
        ticket.updated_at = now

        # Manage lifecycle timestamps
        event_type = EventType.STATUS_CHANGED
        if new_status == TicketStatus.RESOLVED:
            ticket.resolved_at = now
        elif new_status == TicketStatus.CLOSED:
            ticket.closed_at = now
            event_type = EventType.TICKET_CLOSED
        elif old_status in (TicketStatus.RESOLVED, TicketStatus.CLOSED):
            # Reopening
            ticket.reopened_at = now
            event_type = EventType.TICKET_REOPENED

        # Record append-oriented audit entry
        history_entry = TicketEventHistory(
            ticket_id=ticket.id,
            actor_id=actor.id,
            actor_name=actor.display_name,
            actor_type="agent",
            event_type=event_type,
            old_value=old_status,
            new_value=new_status,
            details={"reason": reason} if reason else None,
            created_at=now,
        )
        db.add(history_entry)
        db.commit()
        db.refresh(ticket)
        return ticket
