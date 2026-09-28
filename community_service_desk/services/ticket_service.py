"""Core Ticket CRUD, assignment, and dashboard statistics."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from community_service_desk.models.event_history import EventType, TicketEventHistory
from community_service_desk.models.queue import Queue
from community_service_desk.models.requester import Requester
from community_service_desk.models.ticket import Ticket
from community_service_desk.models.user import User
from community_service_desk.schemas.ticket import DashboardStats, TicketCreate, TicketUpdate
from community_service_desk.services.ticket_lifecycle import TicketStatus


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TicketService:
    """Manages ticket persistence, assignment, and property changes."""

    @staticmethod
    def generate_ticket_number(db: Session, organization_id: str) -> str:
        """Generate the next sequential human-readable ticket number for the organization."""
        count = (
            db.query(func.count(Ticket.id))
            .filter(Ticket.organization_id == organization_id)
            .scalar()
            or 0
        )
        return f"CSD-{count + 1:06d}"

    @classmethod
    def create_ticket(
        cls,
        db: Session,
        organization_id: str,
        data: TicketCreate,
        actor_user: User | None = None,
        requester_user: User | None = None,
    ) -> Ticket:
        """Create a new ticket within an organization."""
        # Resolve requester
        req_email = (
            (
                (data.requester_email or (requester_user.email if requester_user else None))
                or "anonymous@community.org"
            )
            .strip()
            .lower()
        )
        req_name = (
            data.requester_name or (requester_user.display_name if requester_user else None)
        ) or req_email.split("@")[0].title()

        requester = (
            db.query(Requester)
            .filter(
                Requester.organization_id == organization_id,
                Requester.email == req_email,
            )
            .first()
        )
        if not requester:
            requester = Requester(
                organization_id=organization_id,
                user_id=requester_user.id
                if requester_user
                else (actor_user.id if actor_user and actor_user.email == req_email else None),
                email=req_email,
                name=req_name,
            )
            db.add(requester)
            db.flush()

        ticket_number = cls.generate_ticket_number(db, organization_id)

        ticket = Ticket(
            organization_id=organization_id,
            ticket_number=ticket_number,
            requester_id=requester.id,
            title=data.title.strip(),
            description=data.description.strip(),
            status=TicketStatus.NEW,
            priority=data.priority,
            category=data.category,
            tags=data.tags or [],
            queue_id=data.queue_id,
            assigned_agent_id=None,
        )
        db.add(ticket)
        db.flush()

        # Audit creation
        actor_name = actor_user.display_name if actor_user else req_name
        actor_type = "agent" if (actor_user and actor_user.id != requester.user_id) else "requester"

        history = TicketEventHistory(
            ticket_id=ticket.id,
            actor_id=actor_user.id if actor_user else None,
            actor_name=actor_name,
            actor_type=actor_type,
            event_type=EventType.TICKET_CREATED,
            old_value=None,
            new_value=ticket.status,
            details={
                "title": ticket.title,
                "priority": ticket.priority,
                "ticket_number": ticket_number,
            },
        )
        db.add(history)
        db.commit()
        db.refresh(ticket)
        return ticket

    @classmethod
    def assign_ticket(
        cls,
        db: Session,
        ticket: Ticket,
        assigned_agent_id: str | None,
        actor: User,
    ) -> Ticket:
        """Assign or reassign a ticket to an agent, recording an auditable event."""
        if ticket.assigned_agent_id == assigned_agent_id:
            return ticket

        old_agent_id = ticket.assigned_agent_id
        old_agent = db.query(User).filter(User.id == old_agent_id).first() if old_agent_id else None
        new_agent = (
            db.query(User).filter(User.id == assigned_agent_id).first()
            if assigned_agent_id
            else None
        )

        ticket.assigned_agent_id = assigned_agent_id
        ticket.updated_at = utc_now()

        # Automatically transition NEW to OPEN on initial assignment
        if ticket.status == TicketStatus.NEW and assigned_agent_id:
            ticket.status = TicketStatus.OPEN

        history = TicketEventHistory(
            ticket_id=ticket.id,
            actor_id=actor.id,
            actor_name=actor.display_name,
            actor_type="agent",
            event_type=EventType.ASSIGNMENT_CHANGED,
            old_value=old_agent.display_name if old_agent else "Unassigned",
            new_value=new_agent.display_name if new_agent else "Unassigned",
            details={
                "old_agent_id": old_agent_id,
                "new_agent_id": assigned_agent_id,
            },
        )
        db.add(history)
        db.commit()
        db.refresh(ticket)
        return ticket

    @classmethod
    def update_properties(
        cls,
        db: Session,
        ticket: Ticket,
        data: TicketUpdate,
        actor: User,
    ) -> Ticket:
        """Update secondary properties (priority, category, tags, queue) with audit history."""
        now = utc_now()
        ticket.updated_at = now

        if data.priority and data.priority != ticket.priority:
            old_p = ticket.priority
            ticket.priority = data.priority
            db.add(
                TicketEventHistory(
                    ticket_id=ticket.id,
                    actor_id=actor.id,
                    actor_name=actor.display_name,
                    actor_type="agent",
                    event_type=EventType.PRIORITY_CHANGED,
                    old_value=old_p,
                    new_value=data.priority,
                )
            )

        if data.queue_id is not None and data.queue_id != ticket.queue_id:
            old_q = (
                db.query(Queue).filter(Queue.id == ticket.queue_id).first()
                if ticket.queue_id
                else None
            )
            new_q = (
                db.query(Queue).filter(Queue.id == data.queue_id).first() if data.queue_id else None
            )
            ticket.queue_id = data.queue_id
            db.add(
                TicketEventHistory(
                    ticket_id=ticket.id,
                    actor_id=actor.id,
                    actor_name=actor.display_name,
                    actor_type="agent",
                    event_type=EventType.QUEUE_CHANGED,
                    old_value=old_q.name if old_q else "None",
                    new_value=new_q.name if new_q else "None",
                )
            )

        if data.title and data.title.strip() != ticket.title:
            ticket.title = data.title.strip()

        if data.description and data.description.strip() != ticket.description:
            ticket.description = data.description.strip()

        if data.category is not None:
            ticket.category = data.category.strip() if data.category else None

        if data.tags is not None:
            ticket.tags = [t.strip().lower() for t in data.tags if t.strip()]

        db.commit()
        db.refresh(ticket)
        return ticket

    @classmethod
    def get_dashboard_stats(cls, db: Session, organization_id: str) -> DashboardStats:
        """Compute live metric counters for the support dashboard."""
        now = utc_now()
        seven_days_ago = now - timedelta(days=7)

        tickets = db.query(Ticket).filter(Ticket.organization_id == organization_id).all()

        new_c = sum(1 for t in tickets if t.status == TicketStatus.NEW)
        open_c = sum(1 for t in tickets if t.status == TicketStatus.OPEN)
        in_prog_c = sum(1 for t in tickets if t.status == TicketStatus.IN_PROGRESS)
        waiting_c = sum(
            1
            for t in tickets
            if t.status in (TicketStatus.WAITING_ON_REQUESTER, TicketStatus.WAITING_INTERNAL)
        )
        unassigned_c = sum(
            1
            for t in tickets
            if t.assigned_agent_id is None
            and t.status not in (TicketStatus.RESOLVED, TicketStatus.CLOSED)
        )
        resolved_recent_c = sum(
            1
            for t in tickets
            if t.status in (TicketStatus.RESOLVED, TicketStatus.CLOSED)
            and t.resolved_at
            and t.resolved_at >= seven_days_ago
        )

        return DashboardStats(
            new_count=new_c,
            open_count=open_c,
            in_progress_count=in_prog_c,
            waiting_count=waiting_c,
            unassigned_count=unassigned_c,
            resolved_recently_count=resolved_recent_c,
            total_tickets=len(tickets),
        )
