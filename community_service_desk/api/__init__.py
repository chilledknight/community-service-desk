"""Community Service Desk API package."""

from fastapi import APIRouter

from community_service_desk.api.admin import router as admin_router
from community_service_desk.api.attachments import router as attachments_router
from community_service_desk.api.auth import router as auth_router
from community_service_desk.api.conversations import router as conversations_router
from community_service_desk.api.health import router as health_router
from community_service_desk.api.queues import router as queues_router
from community_service_desk.api.resolutions import router as resolutions_router
from community_service_desk.api.search import router as search_router
from community_service_desk.api.tickets import router as tickets_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(tickets_router)
api_router.include_router(conversations_router)
api_router.include_router(resolutions_router)
api_router.include_router(search_router)
api_router.include_router(attachments_router)
api_router.include_router(queues_router)
api_router.include_router(admin_router)

__all__ = ["api_router"]
