"""Tests for Ticket Lifecycle, state transitions, and assignment."""

from community_service_desk.schemas.ticket import TicketCreate
from community_service_desk.services.ticket_lifecycle import TicketStatus
from community_service_desk.services.ticket_service import TicketService


def test_ticket_creation_defaults(db, org_alpha, user_requester_a1):
    ticket = TicketService.create_ticket(
        db=db,
        organization_id=org_alpha.id,
        data=TicketCreate(title="Test Ticket", description="Some description"),
        requester_user=user_requester_a1,
    )
    assert ticket.ticket_number.startswith("CSD-")
    assert ticket.status == TicketStatus.NEW
    assert ticket.priority == "NORMAL"
    assert ticket.assigned_agent_id is None
    assert ticket.resolved_at is None
    assert ticket.closed_at is None


def test_ticket_assignment_transitions_new_to_open(
    client, db, org_alpha, user_requester_a1, user_agent_a, auth_agent_a
):
    ticket = TicketService.create_ticket(
        db=db,
        organization_id=org_alpha.id,
        data=TicketCreate(title="Unassigned Ticket", description="Details"),
        requester_user=user_requester_a1,
    )
    assert ticket.status == TicketStatus.NEW

    # Assign to agent
    resp = client.post(
        f"/api/v1/tickets/{ticket.id}/assign",
        json={"assigned_agent_id": user_agent_a.id},
        headers=auth_agent_a,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["assigned_agent"]["id"] == user_agent_a.id
    assert data["status"] == TicketStatus.OPEN


def test_valid_status_transitions(client, db, org_alpha, user_requester_a1, auth_agent_a):
    ticket = TicketService.create_ticket(
        db=db,
        organization_id=org_alpha.id,
        data=TicketCreate(title="Transition Test", description="Details"),
        requester_user=user_requester_a1,
    )

    # NEW -> IN_PROGRESS
    r1 = client.post(
        f"/api/v1/tickets/{ticket.id}/status", json={"status": "IN_PROGRESS"}, headers=auth_agent_a
    )
    assert r1.status_code == 200
    assert r1.json()["status"] == "IN_PROGRESS"

    # IN_PROGRESS -> WAITING_ON_REQUESTER
    r2 = client.post(
        f"/api/v1/tickets/{ticket.id}/status",
        json={"status": "WAITING_ON_REQUESTER"},
        headers=auth_agent_a,
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "WAITING_ON_REQUESTER"

    # WAITING_ON_REQUESTER -> RESOLVED
    r3 = client.post(
        f"/api/v1/tickets/{ticket.id}/status", json={"status": "RESOLVED"}, headers=auth_agent_a
    )
    assert r3.status_code == 200
    assert r3.json()["status"] == "RESOLVED"

    # RESOLVED -> CLOSED
    r4 = client.post(
        f"/api/v1/tickets/{ticket.id}/status", json={"status": "CLOSED"}, headers=auth_agent_a
    )
    assert r4.status_code == 200
    assert r4.json()["status"] == "CLOSED"


def test_reopen_resolved_and_closed_ticket(client, db, org_alpha, user_requester_a1, auth_agent_a):
    ticket = TicketService.create_ticket(
        db=db,
        organization_id=org_alpha.id,
        data=TicketCreate(title="Reopen Test", description="Details"),
        requester_user=user_requester_a1,
    )

    # Transition to RESOLVED
    client.post(
        f"/api/v1/tickets/{ticket.id}/status", json={"status": "RESOLVED"}, headers=auth_agent_a
    )

    # Reopen to OPEN
    resp_reopen = client.post(
        f"/api/v1/tickets/{ticket.id}/status",
        json={"status": "OPEN", "reason": "Issue recurred"},
        headers=auth_agent_a,
    )
    assert resp_reopen.status_code == 200
    assert resp_reopen.json()["status"] == "OPEN"

    # Close and reopen
    client.post(
        f"/api/v1/tickets/{ticket.id}/status", json={"status": "CLOSED"}, headers=auth_agent_a
    )
    resp_reopen2 = client.post(
        f"/api/v1/tickets/{ticket.id}/status", json={"status": "OPEN"}, headers=auth_agent_a
    )
    assert resp_reopen2.status_code == 200
    assert resp_reopen2.json()["status"] == "OPEN"


def test_invalid_status_transition_rejected(client, db, org_alpha, user_requester_a1, auth_agent_a):
    ticket = TicketService.create_ticket(
        db=db,
        organization_id=org_alpha.id,
        data=TicketCreate(title="Invalid Transition Test", description="Details"),
        requester_user=user_requester_a1,
    )

    # First close the ticket
    client.post(
        f"/api/v1/tickets/{ticket.id}/status", json={"status": "CLOSED"}, headers=auth_agent_a
    )

    # Attempt to go directly from CLOSED to WAITING_ON_REQUESTER (invalid!)
    resp = client.post(
        f"/api/v1/tickets/{ticket.id}/status",
        json={"status": "WAITING_ON_REQUESTER"},
        headers=auth_agent_a,
    )
    assert resp.status_code == 400
    assert "Invalid status transition" in resp.json()["detail"]
