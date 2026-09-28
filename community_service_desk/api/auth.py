"""Authentication API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from community_service_desk.api.deps import get_current_user
from community_service_desk.config import get_settings
from community_service_desk.database import get_db
from community_service_desk.models.user import User
from community_service_desk.schemas.auth import LoginRequest, TokenResponse, UserProfile
from community_service_desk.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
def login(
    req: LoginRequest,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
):
    """Authenticate with email and password and receive a Bearer JWT."""
    result = AuthService.authenticate_user(
        db, req.email, req.password, organization_slug=req.organization_slug
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password, or account inactive.",
        )

    user, org_id, role = result
    token = AuthService.create_access_token(
        data={"sub": user.id, "email": user.email, "org_id": org_id, "role": role}
    )

    settings = get_settings()
    # Set secure session cookie for web browser use
    response.set_cookie(
        key=settings.cookie_name,
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.is_production,
        max_age=settings.access_token_expire_minutes * 60,
    )
    if org_id:
        response.set_cookie(
            key="csd_active_org_id",
            value=org_id,
            httponly=True,
            samesite="lax",
            secure=settings.is_production,
            max_age=settings.access_token_expire_minutes * 60,
        )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        organization_id=org_id,
        role=role,
    )


@router.get("/me", response_model=UserProfile)
def get_me(user: Annotated[User, Depends(get_current_user)]):
    """Get currently authenticated user profile and roles."""
    roles = {m.organization_id: m.role for m in user.memberships}
    return UserProfile(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        active=user.active,
        roles_by_org=roles,
    )


@router.post("/logout")
def logout(response: Response):
    """Clear session cookies."""
    settings = get_settings()
    response.delete_cookie(key=settings.cookie_name)
    response.delete_cookie(key="csd_active_org_id")
    return {"message": "Logged out successfully."}
