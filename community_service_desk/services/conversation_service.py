"""Conversation stream service and server-side internal note boundary enforcement."""

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from community_service_desk.models.conversation import (
    AuthorType,
    EntryType,
    TicketConversation,
)
from community_service_desk.models.event_history import EventType, TicketEventHistory
from community_service_desk.models.ticket import Ticket
from community_service_desk.models.user import User
from community_service_desk.services.authorization_service import AuthorizationService, Roles


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ConversationService:
    """Manages ticket messages with strict server-side boundary enforcement."""

    @classmethod
    def add_entry(
        cls,
        db: Session,
        ticket: Ticket,
        body: str,
        entry_type: str,
        actor: User,
        actor_role: str | None = None,
    ) -> TicketConversation:
        """Create a new reply or internal note with strict role validation."""
        body = body.strip()
        if not body:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Message body cannot be empty.",
            )

        if entry_type not in EntryType.ALL:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid entry type: '{entry_type}'",
            )

        membership = AuthorizationService.get_membership(actor, ticket.organization_id)
        role = actor_role or (membership.role if membership else Roles.REQUESTER)

        # STRICT PRIVACY RULE: Requesters cannot post internal notes
        if entry_type == EntryType.INTERNAL_NOTE and role not in Roles.STAFF_ROLES:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Requesters are not permitted to create internal notes.",
            )

        author_type = AuthorType.AGENT if role in Roles.STAFF_ROLES else AuthorType.REQUESTER
        now = utc_now()

        entry = TicketConversation(
            ticket_id=ticket.id,
            author_id=actor.id,
            author_name=actor.display_name,
            author_type=author_type,
            entry_type=entry_type,
            body=body,
            created_at=now,
        )
        db.add(entry)

        # First response tracking
        if entry_type == EntryType.REQUESTER_VISIBLE_REPLY and author_type == AuthorType.AGENT:
            if ticket.first_response_at is None:
                ticket.first_response_at = now

        ticket.updated_at = now

        # Append to audit history
        hist_event = (
            EventType.INTERNAL_NOTE_ADDED
            if entry_type == EntryType.INTERNAL_NOTE
            else EventType.PUBLIC_REPLY_ADDED
        )
        history = TicketEventHistory(
            ticket_id=ticket.id,
            actor_id=actor.id,
            actor_name=actor.display_name,
            actor_type=author_type,
            event_type=hist_event,
            old_value=None,
            new_value=None,
            details={"entry_id": entry.id, "snippet": body[:80]},
            created_at=now,
        )
        db.add(history)
        db.commit()
        db.refresh(entry)
        return entry

    @classmethod
    def get_visible_entries(
        cls,
        entries: list[TicketConversation],
        user: User,
        organization_id: str,
    ) -> list[TicketConversation]:
        """Filter conversation entries strictly based on server-side authorization.

        CRITICAL SECURITY REQUIREMENT:
        Requesters NEVER receive internal notes in server responses.
        Filtering occurs in Python/SQL before serializing to view or API.
        """
        is_staff = AuthorizationService.can_view_internal_notes(user, organization_id)
        if is_staff:
            return entries

        return [e for e in entries if e.entry_type == EntryType.REQUESTER_VISIBLE_REPLY]
