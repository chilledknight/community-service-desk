"""Ticket data model."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from community_service_desk.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Ticket(Base):
    """Core ticket representing a support request."""

    __tablename__ = "tickets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ticket_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    requester_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("requesters.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[str] = mapped_column(String(50), default="NEW", nullable=False, index=True)
    priority: Mapped[str] = mapped_column(String(50), default="NORMAL", nullable=False, index=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)

    queue_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("queues.id", ondelete="SET NULL"), nullable=True, index=True
    )
    assigned_agent_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    first_response_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reopened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    organization = relationship("Organization", back_populates="tickets")
    requester = relationship("Requester", back_populates="tickets")
    queue = relationship("Queue", back_populates="tickets")
    assigned_agent = relationship(
        "User", back_populates="assigned_tickets", foreign_keys=[assigned_agent_id]
    )

    conversation_entries = relationship(
        "TicketConversation",
        back_populates="ticket",
        cascade="all, delete-orphan",
        order_by="TicketConversation.created_at.asc()",
    )
    history_entries = relationship(
        "TicketEventHistory",
        back_populates="ticket",
        cascade="all, delete-orphan",
        order_by="TicketEventHistory.created_at.asc()",
    )
    resolution = relationship(
        "TicketResolution",
        back_populates="ticket",
        uselist=False,
        cascade="all, delete-orphan",
    )
    attachments = relationship(
        "Attachment",
        back_populates="ticket",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_tickets_org_number", "organization_id", "ticket_number", unique=True),
        Index("ix_tickets_org_status", "organization_id", "status"),
        Index("ix_tickets_org_created", "organization_id", "created_at"),
        Index("ix_tickets_org_queue", "organization_id", "queue_id"),
        Index("ix_tickets_org_agent", "organization_id", "assigned_agent_id"),
    )
