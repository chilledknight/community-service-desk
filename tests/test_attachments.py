"""Tests for Attachment metadata and authorized storage."""

import io

from community_service_desk.schemas.ticket import TicketCreate
from community_service_desk.services.ticket_service import TicketService


def test_upload_valid_attachment(client, db, org_alpha, user_requester_a1, auth_req_a1):
    ticket = TicketService.create_ticket(
        db=db,
        organization_id=org_alpha.id,
        data=TicketCreate(title="Attachment Test", description="Details"),
        requester_user=user_requester_a1,
    )

    file_content = b"Sample log file output: error code 1234"
    files = {"file": ("error_log.txt", io.BytesIO(file_content), "text/plain")}

    resp = client.post(
        f"/api/v1/tickets/{ticket.id}/attachments",
        files=files,
        headers=auth_req_a1,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["filename"] == "error_log.txt"
    assert data["size"] == len(file_content)

    # Download file as authorized requester
    dl_resp = client.get(f"/api/v1/attachments/{data['id']}/download", headers=auth_req_a1)
    assert dl_resp.status_code == 200
    assert dl_resp.content == file_content


def test_dangerous_attachment_extension_rejected(
    client, db, org_alpha, user_requester_a1, auth_req_a1
):
    ticket = TicketService.create_ticket(
        db=db,
        organization_id=org_alpha.id,
        data=TicketCreate(title="Malware Test", description="Details"),
        requester_user=user_requester_a1,
    )

    files = {"file": ("payload.exe", io.BytesIO(b"malicious content"), "application/octet-stream")}
    resp = client.post(
        f"/api/v1/tickets/{ticket.id}/attachments",
        files=files,
        headers=auth_req_a1,
    )
    assert resp.status_code == 400
    assert "Disallowed file extension" in resp.json()["detail"]


def test_unauthorized_user_cannot_download_attachment(
    client, db, org_alpha, user_requester_a1, user_requester_a2, auth_req_a1, auth_req_a2
):
    ticket = TicketService.create_ticket(
        db=db,
        organization_id=org_alpha.id,
        data=TicketCreate(title="Confidential Attachment", description="Details"),
        requester_user=user_requester_a1,
    )

    files = {"file": ("confidential.pdf", io.BytesIO(b"%PDF-1.4 test"), "application/pdf")}
    upload_resp = client.post(
        f"/api/v1/tickets/{ticket.id}/attachments",
        files=files,
        headers=auth_req_a1,
    )
    att_id = upload_resp.json()["id"]

    # Requester 2 (unauthorized for ticket 1) tries to download attachment
    dl_resp = client.get(f"/api/v1/attachments/{att_id}/download", headers=auth_req_a2)
    assert dl_resp.status_code == 403
