"""Organization administration API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from community_service_desk.api.deps import (
    get_current_organization,
    get_current_user,
)
from community_service_desk.database import get_db
from community_service_desk.models.organization import Organization
from community_service_desk.models.user import Membership, User
from community_service_desk.schemas.organization import OrganizationRead
from community_service_desk.schemas.user import MembershipRead, UserCreate
from community_service_desk.services.auth_service import AuthService
from community_service_desk.services.authorization_service import AuthorizationService

router = APIRouter(prefix="/admin", tags=["Administration"])


@router.get("/organization", response_model=OrganizationRead)
def get_organization_profile(
    user: Annotated[User, Depends(get_current_user)],
    org: Annotated[Organization, Depends(get_current_organization)],
):
    """Retrieve active organization details."""
    AuthorizationService.require_admin(user, org.id)
    return org


@router.get("/members", response_model=list[MembershipRead])
def list_organization_members(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    org: Annotated[Organization, Depends(get_current_organization)],
):
    """List all members and their roles for this organization (admin only)."""
    AuthorizationService.require_admin(user, org.id)
    memberships = db.query(Membership).filter(Membership.organization_id == org.id).all()
    return memberships


@router.post("/members", response_model=MembershipRead, status_code=status.HTTP_201_CREATED)
def add_organization_member(
    data: UserCreate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    org: Annotated[Organization, Depends(get_current_organization)],
):
    """Create a new user and add them as a member of this organization (admin only)."""
    AuthorizationService.require_admin(user, org.id)

    target_user = db.query(User).filter(User.email == data.email.strip().lower()).first()
    if not target_user:
        target_user = User(
            email=data.email.strip().lower(),
            display_name=data.display_name.strip(),
            password_hash=AuthService.hash_password(data.password),
            active=True,
        )
        db.add(target_user)
        db.flush()

    existing_mem = (
        db.query(Membership)
        .filter(
            Membership.organization_id == org.id,
            Membership.user_id == target_user.id,
        )
        .first()
    )
    if existing_mem:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already a member of this organization.",
        )

    membership = Membership(
        organization_id=org.id,
        user_id=target_user.id,
        role=data.role,
    )
    db.add(membership)
    db.commit()
    db.refresh(membership)
    return membership
