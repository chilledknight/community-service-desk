"""Ticket Conversation entries (Public Replies and Internal Notes)."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from community_service_desk.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EntryType:
    REQUESTER_VISIBLE_REPLY = "REQUESTER_VISIBLE_REPLY"
    INTERNAL_NOTE = "INTERNAL_NOTE"

    ALL = {REQUESTER_VISIBLE_REPLY, INTERNAL_NOTE}


class AuthorType:
    AGENT = "agent"
    REQUESTER = "requester"
    SYSTEM = "system"

    ALL = {AGENT, REQUESTER, SYSTEM}


class TicketConversation(Base):
    """An entry in the ticket chronological conversation stream."""

    __tablename__ = "ticket_conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ticket_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    author_name: Mapped[str] = mapped_column(String(255), nullable=False)
    author_type: Mapped[str] = mapped_column(String(50), default=AuthorType.AGENT, nullable=False)
    entry_type: Mapped[str] = mapped_column(
        String(50), default=EntryType.REQUESTER_VISIBLE_REPLY, nullable=False, index=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )

    ticket = relationship("Ticket", back_populates="conversation_entries")
    author = relationship("User")

    __table_args__ = (Index("ix_ticket_conv_ticket_type", "ticket_id", "entry_type"),)
