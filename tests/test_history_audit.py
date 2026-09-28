"""Tests for Ticket History and Auditability."""

from community_service_desk.schemas.resolution import ResolutionCreate
from community_service_desk.schemas.ticket import TicketCreate, TicketUpdate
from community_service_desk.services.conversation_service import ConversationService
from community_service_desk.services.resolution_service import ResolutionService
from community_service_desk.services.ticket_lifecycle import TicketLifecycleService
from community_service_desk.services.ticket_service import TicketService


def test_mutations_generate_expected_history_events(
    db, org_alpha, user_requester_a1, user_agent_a, queue_alpha
):
    # 1. Ticket Creation
    ticket = TicketService.create_ticket(
        db=db,
        organization_id=org_alpha.id,
        data=TicketCreate(title="Audit Ticket", description="Details"),
        requester_user=user_requester_a1,
    )
    events = [h.event_type for h in ticket.history_entries]
    assert "TICKET_CREATED" in events

    # 2. Assignment
    TicketService.assign_ticket(db, ticket, user_agent_a.id, actor=user_agent_a)
    db.refresh(ticket)
    events = [h.event_type for h in ticket.history_entries]
    assert "ASSIGNMENT_CHANGED" in events

    # 3. Priority and Queue Change
    TicketService.update_properties(
        db, ticket, TicketUpdate(priority="URGENT", queue_id=queue_alpha.id), actor=user_agent_a
    )
    db.refresh(ticket)
    events = [h.event_type for h in ticket.history_entries]
    assert "PRIORITY_CHANGED" in events
    assert "QUEUE_CHANGED" in events

    # 4. Public reply and Internal note
    ConversationService.add_entry(
        db, ticket, "Hello", "REQUESTER_VISIBLE_REPLY", actor=user_agent_a
    )
    ConversationService.add_entry(db, ticket, "Private note", "INTERNAL_NOTE", actor=user_agent_a)
    db.refresh(ticket)
    events = [h.event_type for h in ticket.history_entries]
    assert "PUBLIC_REPLY_ADDED" in events
    assert "INTERNAL_NOTE_ADDED" in events

    # 5. Resolution recorded
    ResolutionService.record_resolution(
        db,
        ticket,
        ResolutionCreate(
            summary="Fixed problem",
            resolution_steps="Step 1, step 2",
            verification="admin_verified",
            knowledge_useful=True,
        ),
        actor=user_agent_a,
    )
    db.refresh(ticket)
    events = [h.event_type for h in ticket.history_entries]
    assert "RESOLUTION_RECORDED" in events

    # 6. Reopened
    TicketLifecycleService.transition_status(db, ticket, "OPEN", actor=user_agent_a)
    db.refresh(ticket)
    events = [h.event_type for h in ticket.history_entries]
    assert "TICKET_REOPENED" in events

    # 7. Closed
    TicketLifecycleService.transition_status(db, ticket, "CLOSED", actor=user_agent_a)
    db.refresh(ticket)
    events = [h.event_type for h in ticket.history_entries]
    assert "TICKET_CLOSED" in events

    # Verify all entries have valid actor and timestamp
    for h in ticket.history_entries:
        assert h.actor_name is not None
        assert h.created_at is not None
