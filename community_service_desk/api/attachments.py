"""Attachment upload and authorized download endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from community_service_desk.api.deps import (
    get_current_organization,
    get_current_user,
)
from community_service_desk.database import get_db
from community_service_desk.models.attachment import Attachment
from community_service_desk.models.organization import Organization
from community_service_desk.models.ticket import Ticket
from community_service_desk.models.user import User
from community_service_desk.schemas.attachment import AttachmentRead
from community_service_desk.services.attachment_storage_service import AttachmentStorageService
from community_service_desk.services.authorization_service import AuthorizationService

router = APIRouter(tags=["Attachments"])


@router.post(
    "/tickets/{ticket_id}/attachments",
    response_model=AttachmentRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_attachment(
    ticket_id: str,
    file: Annotated[UploadFile, File(...)],
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    org: Annotated[Organization, Depends(get_current_organization)],
):
    """Upload a file attachment to a ticket."""
    ticket = (
        db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.organization_id == org.id).first()
    )
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found.")

    AuthorizationService.assert_ticket_access(user, ticket)

    attachment = await AttachmentStorageService.save_attachment(
        db=db,
        ticket=ticket,
        file=file,
        actor=user,
    )
    return attachment


@router.get("/tickets/{ticket_id}/attachments", response_model=list[AttachmentRead])
def list_ticket_attachments(
    ticket_id: str,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    org: Annotated[Organization, Depends(get_current_organization)],
):
    """List attachment metadata for a ticket."""
    ticket = (
        db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.organization_id == org.id).first()
    )
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found.")

    AuthorizationService.assert_ticket_access(user, ticket)
    return ticket.attachments


@router.get("/attachments/{attachment_id}/download")
def download_attachment(
    attachment_id: str,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    """Securely download an attachment after verifying tenant authorization."""
    attachment = db.query(Attachment).filter(Attachment.id == attachment_id).first()
    if not attachment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found.")

    ticket = db.query(Ticket).filter(Ticket.id == attachment.ticket_id).first()
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Associated ticket not found."
        )

    # Authorize access
    AuthorizationService.assert_ticket_access(user, ticket)

    file_path = AttachmentStorageService.get_file_path(attachment)
    return FileResponse(
        path=file_path,
        filename=attachment.filename,
        media_type=attachment.content_type,
    )
