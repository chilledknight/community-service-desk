"""Structured Resolution model for knowledge capture and future AI assistance."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from community_service_desk.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class VerificationMethod:
    REQUESTER_CONFIRMED = "requester_confirmed"
    ADMIN_VERIFIED = "admin_verified"
    AUTOMATED_TEST_PASSED = "automated_test_passed"
    NO_LONGER_REPRODUCIBLE = "no_longer_reproducible"
    WORKAROUND_CONFIRMED = "workaround_confirmed"

    ALL = {
        REQUESTER_CONFIRMED,
        ADMIN_VERIFIED,
        AUTOMATED_TEST_PASSED,
        NO_LONGER_REPRODUCIBLE,
        WORKAROUND_CONFIRMED,
    }


class TicketResolution(Base):
    """Structured resolution information supporting knowledge preservation and retrieval."""

    __tablename__ = "ticket_resolutions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ticket_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tickets.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    resolved_by_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    summary: Mapped[str] = mapped_column(Text, nullable=False)
    root_cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution_steps: Mapped[str] = mapped_column(Text, nullable=False)
    verification: Mapped[str] = mapped_column(
        String(100), default=VerificationMethod.ADMIN_VERIFIED, nullable=False
    )
    knowledge_useful: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    ticket = relationship("Ticket", back_populates="resolution")
    organization = relationship("Organization", back_populates="resolutions")
    resolved_by = relationship("User", back_populates="resolutions")

    __table_args__ = (Index("ix_resolutions_org_useful", "organization_id", "knowledge_useful"),)
