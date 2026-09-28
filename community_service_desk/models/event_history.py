"""Ticket Event History model for append-only audit tracking."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from community_service_desk.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EventType:
    TICKET_CREATED = "TICKET_CREATED"
    STATUS_CHANGED = "STATUS_CHANGED"
    PRIORITY_CHANGED = "PRIORITY_CHANGED"
    QUEUE_CHANGED = "QUEUE_CHANGED"
    ASSIGNMENT_CHANGED = "ASSIGNMENT_CHANGED"
    PUBLIC_REPLY_ADDED = "PUBLIC_REPLY_ADDED"
    INTERNAL_NOTE_ADDED = "INTERNAL_NOTE_ADDED"
    RESOLUTION_RECORDED = "RESOLUTION_RECORDED"
    TICKET_REOPENED = "TICKET_REOPENED"
    TICKET_CLOSED = "TICKET_CLOSED"

    ALL = {
        TICKET_CREATED,
        STATUS_CHANGED,
        PRIORITY_CHANGED,
        QUEUE_CHANGED,
        ASSIGNMENT_CHANGED,
        PUBLIC_REPLY_ADDED,
        INTERNAL_NOTE_ADDED,
        RESOLUTION_RECORDED,
        TICKET_REOPENED,
        TICKET_CLOSED,
    }


class TicketEventHistory(Base):
    """Append-only audit trail recording state transitions and actions on a ticket."""

    __tablename__ = "ticket_event_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ticket_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    actor_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    actor_name: Mapped[str] = mapped_column(String(255), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(50), default="agent", nullable=False)

    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    old_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    new_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )

    ticket = relationship("Ticket", back_populates="history_entries")
    actor = relationship("User")

    __table_args__ = (Index("ix_history_ticket_created", "ticket_id", "created_at"),)
