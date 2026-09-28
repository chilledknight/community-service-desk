"""Tests for Requester Authorization."""

from community_service_desk.schemas.ticket import TicketCreate
from community_service_desk.services.ticket_service import TicketService


def test_requester_can_view_own_ticket(client, db, org_alpha, user_requester_a1, auth_req_a1):
    ticket = TicketService.create_ticket(
        db=db,
        organization_id=org_alpha.id,
        data=TicketCreate(title="Requester 1 Issue", description="Help with login"),
        requester_user=user_requester_a1,
    )

    response = client.get(f"/api/v1/tickets/{ticket.id}", headers=auth_req_a1)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == ticket.id
    assert data["title"] == "Requester 1 Issue"


def test_requester_cannot_view_other_requester_ticket(
    client, db, org_alpha, user_requester_a1, user_requester_a2, auth_req_a2
):
    # Requester 1 creates a private ticket
    ticket1 = TicketService.create_ticket(
        db=db,
        organization_id=org_alpha.id,
        data=TicketCreate(title="Requester 1 Confidential", description="Private issue"),
        requester_user=user_requester_a1,
    )

    # Requester 2 attempts to fetch Requester 1's ticket
    response = client.get(f"/api/v1/tickets/{ticket1.id}", headers=auth_req_a2)
    assert response.status_code == 403
    assert "not authorized" in response.json()["detail"].lower()


def test_requester_ticket_list_is_scoped_to_self(
    client, db, org_alpha, user_requester_a1, user_requester_a2, auth_req_a1, auth_req_a2
):
    # Ticket for user 1
    t1 = TicketService.create_ticket(
        db=db,
        organization_id=org_alpha.id,
        data=TicketCreate(title="Ticket for User 1", description="Details 1"),
        requester_user=user_requester_a1,
    )
    # Ticket for user 2
    t2 = TicketService.create_ticket(
        db=db,
        organization_id=org_alpha.id,
        data=TicketCreate(title="Ticket for User 2", description="Details 2"),
        requester_user=user_requester_a2,
    )

    # User 1 lists tickets
    resp1 = client.get("/api/v1/tickets", headers=auth_req_a1)
    assert resp1.status_code == 200
    ids_1 = [t["id"] for t in resp1.json()]
    assert t1.id in ids_1
    assert t2.id not in ids_1


def test_requester_cannot_modify_ticket_status_or_assignment(
    client, db, org_alpha, user_requester_a1, auth_req_a1
):
    ticket = TicketService.create_ticket(
        db=db,
        organization_id=org_alpha.id,
        data=TicketCreate(title="My Ticket", description="Details"),
        requester_user=user_requester_a1,
    )

    # Attempt to transition status
    resp_status = client.post(
        f"/api/v1/tickets/{ticket.id}/status",
        json={"status": "RESOLVED"},
        headers=auth_req_a1,
    )
    assert resp_status.status_code == 403

    # Attempt to assign
    resp_assign = client.post(
        f"/api/v1/tickets/{ticket.id}/assign",
        json={"assigned_agent_id": user_requester_a1.id},
        headers=auth_req_a1,
    )
    assert resp_assign.status_code == 403
