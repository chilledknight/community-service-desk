"""Resolution service for structured resolution capture and preservation."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from community_service_desk.models.event_history import EventType, TicketEventHistory
from community_service_desk.models.resolution import TicketResolution
from community_service_desk.models.ticket import Ticket
from community_service_desk.models.user import User
from community_service_desk.schemas.resolution import ResolutionCreate
from community_service_desk.services.ticket_lifecycle import TicketStatus


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ResolutionService:
    """Manages structured ticket resolutions and knowledge preservation flags."""

    @classmethod
    def record_resolution(
        cls,
        db: Session,
        ticket: Ticket,
        data: ResolutionCreate,
        actor: User,
    ) -> TicketResolution:
        """Create or update structured resolution data, transition status to RESOLVED, and log event."""
        now = utc_now()

        resolution = (
            db.query(TicketResolution).filter(TicketResolution.ticket_id == ticket.id).first()
        )

        is_new = resolution is None
        if is_new:
            resolution = TicketResolution(
                ticket_id=ticket.id,
                organization_id=ticket.organization_id,
                resolved_by_id=actor.id,
                summary=data.summary.strip(),
                root_cause=data.root_cause.strip() if data.root_cause else None,
                resolution_steps=data.resolution_steps.strip(),
                verification=data.verification,
                knowledge_useful=data.knowledge_useful,
                created_at=now,
                updated_at=now,
            )
            db.add(resolution)
        else:
            resolution.resolved_by_id = actor.id
            resolution.summary = data.summary.strip()
            resolution.root_cause = data.root_cause.strip() if data.root_cause else None
            resolution.resolution_steps = data.resolution_steps.strip()
            resolution.verification = data.verification
            resolution.knowledge_useful = data.knowledge_useful
            resolution.updated_at = now

        # Transition ticket status to RESOLVED if not already
        if ticket.status != TicketStatus.RESOLVED:
            old_status = ticket.status
            ticket.status = TicketStatus.RESOLVED
            ticket.resolved_at = now
            ticket.updated_at = now

            db.add(
                TicketEventHistory(
                    ticket_id=ticket.id,
                    actor_id=actor.id,
                    actor_name=actor.display_name,
                    actor_type="agent",
                    event_type=EventType.STATUS_CHANGED,
                    old_value=old_status,
                    new_value=TicketStatus.RESOLVED,
                    details={"action": "ticket_resolved"},
                    created_at=now,
                )
            )

        # Audit resolution record
        db.add(
            TicketEventHistory(
                ticket_id=ticket.id,
                actor_id=actor.id,
                actor_name=actor.display_name,
                actor_type="agent",
                event_type=EventType.RESOLUTION_RECORDED,
                old_value=None,
                new_value="RESOLVED",
                details={
                    "knowledge_useful": data.knowledge_useful,
                    "verification": data.verification,
                    "summary_snippet": data.summary[:80],
                },
                created_at=now,
            )
        )

        db.commit()
        db.refresh(resolution)
        return resolution
