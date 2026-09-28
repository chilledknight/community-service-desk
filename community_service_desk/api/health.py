"""Health and status endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from community_service_desk import __version__
from community_service_desk.database import get_db

router = APIRouter(tags=["Health"])


@router.get("/health")
def health_check(db: Annotated[Session, Depends(get_db)]):
    """Health check endpoint verifying database connectivity."""
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    return {
        "status": "healthy" if db_ok else "unhealthy",
        "service": "community-service-desk",
        "version": __version__,
        "database": "connected" if db_ok else "disconnected",
    }
