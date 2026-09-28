"""Tests specifically proving the Server-Side Internal Note Privacy Boundary."""

from community_service_desk.schemas.ticket import TicketCreate
from community_service_desk.services.conversation_service import ConversationService
from community_service_desk.services.ticket_service import TicketService


def test_agent_can_create_and_view_internal_note(
    client, db, org_alpha, user_requester_a1, user_agent_a, auth_agent_a
):
    ticket = TicketService.create_ticket(
        db=db,
        organization_id=org_alpha.id,
        data=TicketCreate(title="Printer Issue", description="Details"),
        requester_user=user_requester_a1,
    )

    # Agent creates internal note
    resp = client.post(
        f"/api/v1/tickets/{ticket.id}/conversations",
        json={
            "body": "Private troubleshooting note: Spooler credentials need rotation.",
            "entry_type": "INTERNAL_NOTE",
        },
        headers=auth_agent_a,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["entry_type"] == "INTERNAL_NOTE"

    # Agent views conversation list
    list_resp = client.get(f"/api/v1/tickets/{ticket.id}/conversations", headers=auth_agent_a)
    assert list_resp.status_code == 200
    entries = list_resp.json()
    assert any(e["entry_type"] == "INTERNAL_NOTE" for e in entries)


def test_requester_cannot_view_or_serialize_internal_notes(
    client, db, org_alpha, user_requester_a1, user_agent_a, auth_req_a1, auth_agent_a
):
    """CRITICAL SECURITY TEST:
    Proves that internal notes are completely filtered out on the server before
    the JSON response is serialized for a requester.
    """
    ticket = TicketService.create_ticket(
        db=db,
        organization_id=org_alpha.id,
        data=TicketCreate(title="Password Reset", description="Cannot login"),
        requester_user=user_requester_a1,
    )

    # 1. Agent adds a public reply
    ConversationService.add_entry(
        db=db,
        ticket=ticket,
        body="Public message: Hello, we are looking into this.",
        entry_type="REQUESTER_VISIBLE_REPLY",
        actor=user_agent_a,
    )

    # 2. Agent adds a confidential internal note
    secret_text = "CONFIDENTIAL INTERNAL AGENT NOTE: User account flagged for security audit."
    ConversationService.add_entry(
        db=db,
        ticket=ticket,
        body=secret_text,
        entry_type="INTERNAL_NOTE",
        actor=user_agent_a,
    )

    # 3. Requester queries conversations endpoint
    conv_resp = client.get(f"/api/v1/tickets/{ticket.id}/conversations", headers=auth_req_a1)
    assert conv_resp.status_code == 200
    conv_entries = conv_resp.json()

    # Verify no entry has entry_type == INTERNAL_NOTE or contains the secret text
    assert len(conv_entries) == 1
    assert conv_entries[0]["body"] == "Public message: Hello, we are looking into this."
    for e in conv_entries:
        assert e["entry_type"] != "INTERNAL_NOTE"
        assert secret_text not in e["body"]

    # 4. Requester queries ticket detail endpoint
    detail_resp = client.get(f"/api/v1/tickets/{ticket.id}", headers=auth_req_a1)
    assert detail_resp.status_code == 200
    ticket_data = detail_resp.json()

    # The serialized conversation_entries must NOT contain the internal note
    assert "conversation_entries" in ticket_data
    assert len(ticket_data["conversation_entries"]) == 1
    assert secret_text not in str(ticket_data)


def test_requester_cannot_create_internal_notes(
    client, db, org_alpha, user_requester_a1, auth_req_a1
):
    ticket = TicketService.create_ticket(
        db=db,
        organization_id=org_alpha.id,
        data=TicketCreate(title="Network issue", description="Details"),
        requester_user=user_requester_a1,
    )

    # Requester attempts to post an INTERNAL_NOTE
    resp = client.post(
        f"/api/v1/tickets/{ticket.id}/conversations",
        json={
            "body": "Requester attempting to bypass note boundary",
            "entry_type": "INTERNAL_NOTE",
        },
        headers=auth_req_a1,
    )
    assert resp.status_code == 403
    assert "not permitted to create internal notes" in resp.json()["detail"].lower()
