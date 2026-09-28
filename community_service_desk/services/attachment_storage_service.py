"""Attachment storage abstraction and file authorization."""

import os
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from community_service_desk.config import get_settings
from community_service_desk.models.attachment import Attachment
from community_service_desk.models.ticket import Ticket
from community_service_desk.models.user import User

DANGEROUS_EXTENSIONS = {
    ".exe",
    ".bat",
    ".cmd",
    ".sh",
    ".bash",
    ".vbs",
    ".ps1",
    ".msi",
    ".dll",
    ".scr",
    ".com",
}


class AttachmentStorageService:
    """Safe storage abstraction for local filesystem and future object storage backends."""

    @classmethod
    def validate_file(cls, file: UploadFile) -> None:
        """Validate filename and extension safety."""
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Filename cannot be empty.",
            )

        ext = Path(file.filename).suffix.lower()
        if ext in DANGEROUS_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Upload rejected: Disallowed file extension '{ext}' for security.",
            )

    @classmethod
    async def save_attachment(
        cls,
        db: Session,
        ticket: Ticket,
        file: UploadFile,
        actor: User,
    ) -> Attachment:
        """Read bytes, validate size, write to private disk storage, and persist metadata."""
        cls.validate_file(file)
        settings = get_settings()

        content = await file.read()
        size = len(content)

        if size > settings.max_upload_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds maximum upload size limit ({settings.max_upload_bytes // (1024 * 1024)} MB).",
            )

        ext = Path(file.filename or "file").suffix.lower()
        safe_key = f"{uuid.uuid4().hex}{ext}"

        upload_dir = settings.uploads_path
        dest_path = upload_dir / safe_key

        with open(dest_path, "wb") as f:
            f.write(content)

        attachment = Attachment(
            organization_id=ticket.organization_id,
            ticket_id=ticket.id,
            filename=file.filename or "attachment",
            content_type=file.content_type or "application/octet-stream",
            size=size,
            storage_key=safe_key,
            uploaded_by_id=actor.id,
        )
        db.add(attachment)
        db.commit()
        db.refresh(attachment)
        return attachment

    @classmethod
    def get_file_path(cls, attachment: Attachment) -> Path:
        """Resolve physical path on disk with path-traversal prevention."""
        settings = get_settings()
        safe_name = os.path.basename(attachment.storage_key)
        target = settings.uploads_path / safe_name
        if not target.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Attachment file content not found on server.",
            )
        return target
