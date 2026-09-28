"""Tests for Structured Resolution capture and preservation."""

from community_service_desk.schemas.resolution import ResolutionCreate
from community_service_desk.schemas.ticket import TicketCreate
from community_service_desk.services.resolution_service import ResolutionService
from community_service_desk.services.ticket_service import TicketService


def test_structured_resolution_stored_and_retrieved(
    client, db, org_alpha, user_requester_a1, user_agent_a, auth_agent_a
):
    ticket = TicketService.create_ticket(
        db=db,
        organization_id=org_alpha.id,
        data=TicketCreate(title="Printer mapping vanished", description="Details"),
        requester_user=user_requester_a1,
    )

    resolution_data = {
        "summary": "Reinstalled printer mapping and forced group policy update.",
        "root_cause": "GPO link had drifted after controller maintenance.",
        "resolution_steps": "1. Re-linked GPO.\n2. Ran gpupdate /force.\n3. Verified spooler.",
        "verification": "requester_confirmed",
        "knowledge_useful": True,
    }

    # Record resolution via API
    resp = client.post(
        f"/api/v1/tickets/{ticket.id}/resolution",
        json=resolution_data,
        headers=auth_agent_a,
    )
    assert resp.status_code == 201
    res = resp.json()
    assert res["summary"] == resolution_data["summary"]
    assert res["root_cause"] == resolution_data["root_cause"]
    assert res["resolution_steps"] == resolution_data["resolution_steps"]
    assert res["verification"] == "requester_confirmed"
    assert res["knowledge_useful"] is True

    # Verify ticket status automatically became RESOLVED
    db.refresh(ticket)
    assert ticket.status == "RESOLVED"
    assert ticket.resolved_at is not None

    # Fetch resolution independently
    fetch_resp = client.get(f"/api/v1/tickets/{ticket.id}/resolution", headers=auth_agent_a)
    assert fetch_resp.status_code == 200
    assert fetch_resp.json()["id"] == res["id"]


def test_knowledge_usefulness_flag_preserved(db, org_alpha, user_requester_a1, user_agent_a):
    ticket = TicketService.create_ticket(
        db=db,
        organization_id=org_alpha.id,
        data=TicketCreate(title="Special Issue", description="Details"),
        requester_user=user_requester_a1,
    )

    res = ResolutionService.record_resolution(
        db=db,
        ticket=ticket,
        data=ResolutionCreate(
            summary="Custom patch applied",
            resolution_steps="Step 1",
            verification="admin_verified",
            knowledge_useful=True,
        ),
        actor=user_agent_a,
    )
    assert res.knowledge_useful is True
