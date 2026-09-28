"""Search and Knowledge Retrieval API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from community_service_desk.api.deps import (
    get_current_membership,
    get_current_organization,
    get_current_user,
)
from community_service_desk.database import get_db
from community_service_desk.models.organization import Organization
from community_service_desk.models.user import Membership, User
from community_service_desk.schemas.search import (
    KnowledgeEvidence,
    KnowledgeSearchQuery,
    TicketSearchFilter,
)
from community_service_desk.schemas.ticket import TicketListItem
from community_service_desk.services.authorization_service import AuthorizationService, Roles
from community_service_desk.services.knowledge_retrieval_service import KnowledgeRetrievalService
from community_service_desk.services.search_service import SearchService

router = APIRouter(prefix="/search", tags=["Search & Knowledge Retrieval"])


@router.post("/tickets", response_model=list[TicketListItem])
def search_tickets(
    filters: TicketSearchFilter,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    org: Annotated[Organization, Depends(get_current_organization)],
    membership: Annotated[Membership, Depends(get_current_membership)],
):
    """Execute multi-attribute and text search within active organization boundaries."""
    is_staff = membership.role in Roles.STAFF_ROLES
    req_uid = None if is_staff else user.id
    req_email = None if is_staff else user.email

    results = SearchService.search_tickets(
        db=db,
        organization_id=org.id,
        filters=filters,
        requester_user_id=req_uid,
        requester_email=req_email,
    )
    return results


@router.post("/knowledge", response_model=list[KnowledgeEvidence])
def search_knowledge_base(
    query: KnowledgeSearchQuery,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    org: Annotated[Organization, Depends(get_current_organization)],
):
    """Retrieve historical resolution evidence using the KnowledgeRetrievalService abstraction."""
    # Enforce staff authorization for knowledge base retrieval
    AuthorizationService.require_agent(user, org.id)

    evidence = KnowledgeRetrievalService.retrieve_evidence(
        db=db,
        organization_id=org.id,
        query=query.query,
        category=query.category,
        tags=query.tags,
        limit=query.limit,
    )
    return evidence
