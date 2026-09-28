"""FastAPI dependency injection utilities."""

from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from community_service_desk.config import get_settings
from community_service_desk.database import get_db
from community_service_desk.models.organization import Organization
from community_service_desk.models.user import Membership, User
from community_service_desk.services.auth_service import AuthService
from community_service_desk.services.authorization_service import AuthorizationService

security = HTTPBearer(auto_error=False)


def get_token_from_request(
    request: Request,
    bearer_auth: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> str | None:
    """Extract token either from Bearer Authorization header or session cookie."""
    if bearer_auth and bearer_auth.credentials:
        return bearer_auth.credentials

    settings = get_settings()
    cookie_token = request.cookies.get(settings.cookie_name)
    if cookie_token:
        return cookie_token

    return None


def get_current_user(
    db: Annotated[Session, Depends(get_db)],
    token: Annotated[str | None, Depends(get_token_from_request)],
) -> User:
    """Resolve and authenticate the user from JWT token."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a Bearer token or login.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = AuthService.decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload["sub"]
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive or not found.",
        )

    return user


def get_current_organization(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    x_org_slug: Annotated[str | None, Header(alias="X-Organization-Slug")] = None,
    x_org_id: Annotated[str | None, Header(alias="X-Organization-ID")] = None,
) -> Organization:
    """Resolve current organization context from headers, session cookie, or primary membership."""
    org: Organization | None = None

    if x_org_id:
        org = db.query(Organization).filter(Organization.id == x_org_id).first()
    elif x_org_slug:
        org = db.query(Organization).filter(Organization.slug == x_org_slug).first()
    else:
        # Check session cookie for active org
        cookie_org_id = request.cookies.get("csd_active_org_id")
        if cookie_org_id:
            org = db.query(Organization).filter(Organization.id == cookie_org_id).first()

    # Fallback to user's first active organization membership
    if not org and user.memberships:
        first_mem = user.memberships[0]
        org = db.query(Organization).filter(Organization.id == first_mem.organization_id).first()

    if not org or org.status != "active":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active organization context could not be resolved.",
        )

    # Validate that current user is indeed a member of this organization
    AuthorizationService.require_organization_member(user, org.id)
    return org


def get_current_membership(
    user: Annotated[User, Depends(get_current_user)],
    org: Annotated[Organization, Depends(get_current_organization)],
) -> Membership:
    """Resolve user's verified membership record within current organization."""
    return AuthorizationService.require_organization_member(user, org.id)


def require_agent_user(
    user: Annotated[User, Depends(get_current_user)],
    org: Annotated[Organization, Depends(get_current_organization)],
) -> tuple[User, Organization, Membership]:
    """Dependency asserting agent or administrator privileges."""
    membership = AuthorizationService.require_agent(user, org.id)
    return user, org, membership


def require_admin_user(
    user: Annotated[User, Depends(get_current_user)],
    org: Annotated[Organization, Depends(get_current_organization)],
) -> tuple[User, Organization, Membership]:
    """Dependency asserting organization administrator privileges."""
    membership = AuthorizationService.require_admin(user, org.id)
    return user, org, membership
