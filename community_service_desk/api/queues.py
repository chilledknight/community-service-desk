"""Queue management endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from community_service_desk.api.deps import (
    get_current_organization,
    get_current_user,
)
from community_service_desk.database import get_db
from community_service_desk.models.organization import Organization
from community_service_desk.models.queue import Queue
from community_service_desk.models.user import User
from community_service_desk.schemas.queue import QueueCreate, QueueRead
from community_service_desk.services.authorization_service import AuthorizationService

router = APIRouter(prefix="/queues", tags=["Queues"])


@router.get("", response_model=list[QueueRead])
def list_queues(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    org: Annotated[Organization, Depends(get_current_organization)],
):
    """List queues for the active organization."""
    queues = (
        db.query(Queue)
        .filter(Queue.organization_id == org.id, Queue.active.is_(True))
        .order_by(Queue.name.asc())
        .all()
    )
    return queues


@router.post("", response_model=QueueRead, status_code=status.HTTP_201_CREATED)
def create_queue(
    data: QueueCreate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    org: Annotated[Organization, Depends(get_current_organization)],
):
    """Create a new queue (admin only)."""
    AuthorizationService.require_admin(user, org.id)

    existing = (
        db.query(Queue)
        .filter(Queue.organization_id == org.id, Queue.name == data.name.strip())
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Queue with name '{data.name}' already exists in this organization.",
        )

    queue = Queue(
        organization_id=org.id,
        name=data.name.strip(),
        description=data.description.strip() if data.description else None,
        active=data.active,
    )
    db.add(queue)
    db.commit()
    db.refresh(queue)
    return queue
