"""Tests for Organization Isolation and Tenant Boundaries."""

from community_service_desk.schemas.ticket import TicketCreate
from community_service_desk.services.ticket_service import TicketService


def test_user_cannot_access_other_organization_ticket(
    client, db, org_alpha, org_beta, auth_agent_a, auth_agent_b, user_agent_b, user_requester_a1
):
    # Create ticket in Org B
    ticket_b = TicketService.create_ticket(
        db=db,
        organization_id=org_beta.id,
        data=TicketCreate(title="Beta confidential ticket", description="Private issue in Org B"),
        actor_user=user_agent_b,
    )

    # Agent A in Org A attempts to access ticket in Org B
    response = client.get(f"/api/v1/tickets/{ticket_b.id}", headers=auth_agent_a)
    # Server-side boundary concealment: returns 404
    assert response.status_code == 404
    assert "Ticket not found" in response.json()["detail"]


def test_agent_cannot_enumerate_other_org_tickets(
    client, db, org_alpha, org_beta, auth_agent_a, auth_agent_b, user_agent_b
):
    # Create ticket in Org B
    ticket_b = TicketService.create_ticket(
        db=db,
        organization_id=org_beta.id,
        data=TicketCreate(title="Beta ticket secret", description="Should never leak to Org A"),
        actor_user=user_agent_b,
    )

    # Agent A queries ticket list with Org A context
    response = client.get("/api/v1/tickets", headers=auth_agent_a)
    assert response.status_code == 200
    ticket_ids = [t["id"] for t in response.json()]
    assert ticket_b.id not in ticket_ids

    # Agent A tries to forge header X-Organization-ID to Org B
    forged_headers = auth_agent_a.copy()
    forged_headers["X-Organization-ID"] = org_beta.id
    response_forged = client.get("/api/v1/tickets", headers=forged_headers)
    # Access denied because Agent A is not a member of Org B
    assert response_forged.status_code == 403


def test_agent_cannot_modify_other_org_ticket(client, db, org_beta, auth_agent_a, user_agent_b):
    ticket_b = TicketService.create_ticket(
        db=db,
        organization_id=org_beta.id,
        data=TicketCreate(title="Org B Ticket", description="Do not touch"),
        actor_user=user_agent_b,
    )

    response = client.post(
        f"/api/v1/tickets/{ticket_b.id}/status",
        json={"status": "IN_PROGRESS"},
        headers=auth_agent_a,
    )
    assert response.status_code == 404
