"""Organization data model."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from community_service_desk.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Organization(Base):
    """An organization/workspace tenant in Community Service Desk."""

    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    # Relationships
    memberships = relationship(
        "Membership", back_populates="organization", cascade="all, delete-orphan"
    )
    requesters = relationship(
        "Requester", back_populates="organization", cascade="all, delete-orphan"
    )
    queues = relationship("Queue", back_populates="organization", cascade="all, delete-orphan")
    tickets = relationship("Ticket", back_populates="organization", cascade="all, delete-orphan")
    resolutions = relationship(
        "TicketResolution", back_populates="organization", cascade="all, delete-orphan"
    )
    attachments = relationship(
        "Attachment", back_populates="organization", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_organizations_status", "status"),)
