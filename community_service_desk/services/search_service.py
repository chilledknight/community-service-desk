"""Multi-attribute and text search across tickets and resolutions."""

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from community_service_desk.models.requester import Requester
from community_service_desk.models.resolution import TicketResolution
from community_service_desk.models.ticket import Ticket
from community_service_desk.schemas.search import TicketSearchFilter


class SearchService:
    """Performs tenant-isolated searches over tickets, metadata, and structured resolutions."""

    @classmethod
    def search_tickets(
        cls,
        db: Session,
        organization_id: str,
        filters: TicketSearchFilter,
        requester_user_id: str | None = None,
        requester_email: str | None = None,
    ) -> list[Ticket]:
        """Search and filter tickets within an organization.

        ORGANIZATION ISOLATION:
        The query is unconditionally scoped to `organization_id`.
        If requester credentials are provided (i.e. non-staff user), results are
        further scoped to the requester's own tickets.
        """
        query = (
            db.query(Ticket)
            .filter(Ticket.organization_id == organization_id)
            .outerjoin(Ticket.requester)
            .outerjoin(Ticket.resolution)
            .options(
                joinedload(Ticket.requester),
                joinedload(Ticket.queue),
                joinedload(Ticket.assigned_agent),
                joinedload(Ticket.resolution),
            )
        )

        # Scoping for non-staff requester users
        if requester_user_id or requester_email:
            req_conds = []
            if requester_user_id:
                req_conds.append(Requester.user_id == requester_user_id)
            if requester_email:
                req_conds.append(Requester.email.ilike(requester_email))
            query = query.filter(or_(*req_conds))

        # Filter by Ticket Number
        if filters.ticket_number:
            query = query.filter(Ticket.ticket_number.ilike(f"%{filters.ticket_number.strip()}%"))

        # Filter by Status
        if filters.status:
            query = query.filter(Ticket.status == filters.status.upper())

        # Filter by Priority
        if filters.priority:
            query = query.filter(Ticket.priority == filters.priority.upper())

        # Filter by Queue
        if filters.queue_id:
            query = query.filter(Ticket.queue_id == filters.queue_id)

        # Filter by Assigned Agent
        if filters.assigned_agent_id:
            query = query.filter(Ticket.assigned_agent_id == filters.assigned_agent_id)

        # Filter by Category
        if filters.category:
            query = query.filter(Ticket.category.ilike(f"%{filters.category.strip()}%"))

        # Filter by Requester name or email
        if filters.requester:
            term = f"%{filters.requester.strip()}%"
            query = query.filter(or_(Requester.name.ilike(term), Requester.email.ilike(term)))

        # Date Filters
        if filters.created_after:
            query = query.filter(Ticket.created_at >= filters.created_after)
        if filters.created_before:
            query = query.filter(Ticket.created_at <= filters.created_before)
        if filters.resolved_after:
            query = query.filter(Ticket.resolved_at >= filters.resolved_after)
        if filters.resolved_before:
            query = query.filter(Ticket.resolved_at <= filters.resolved_before)

        # Free-text search over title, description, resolution summary, and root cause
        if filters.query:
            q_term = f"%{filters.query.strip()}%"
            query = query.filter(
                or_(
                    Ticket.title.ilike(q_term),
                    Ticket.description.ilike(q_term),
                    TicketResolution.summary.ilike(q_term),
                    TicketResolution.root_cause.ilike(q_term),
                    TicketResolution.resolution_steps.ilike(q_term),
                )
            )

        # Execute query
        results = (
            query.order_by(Ticket.created_at.desc())
            .offset(filters.offset)
            .limit(filters.limit)
            .all()
        )

        # Filter by tag in Python to ensure compatibility across SQLite and Postgres JSON structures
        if filters.tag:
            target_tag = filters.tag.strip().lower()
            results = [
                t for t in results if any(target_tag in str(tag).lower() for tag in (t.tags or []))
            ]

        return results
