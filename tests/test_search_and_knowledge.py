"""Tests for Search and Knowledge Retrieval Service."""

from community_service_desk.schemas.resolution import ResolutionCreate
from community_service_desk.schemas.search import TicketSearchFilter
from community_service_desk.schemas.ticket import TicketCreate
from community_service_desk.services.knowledge_retrieval_service import KnowledgeRetrievalService
from community_service_desk.services.resolution_service import ResolutionService
from community_service_desk.services.search_service import SearchService
from community_service_desk.services.ticket_service import TicketService


def test_search_filters_and_text_queries(
    db, org_alpha, user_requester_a1, user_agent_a, queue_alpha
):
    # Ticket 1
    t1 = TicketService.create_ticket(
        db=db,
        organization_id=org_alpha.id,
        data=TicketCreate(
            title="Printer driver fault on Win11",
            description="Driver crash error code 0x0028",
            priority="HIGH",
            category="Hardware",
            tags=["printer", "win11"],
            queue_id=queue_alpha.id,
        ),
        requester_user=user_requester_a1,
    )

    # Ticket 2
    t2 = TicketService.create_ticket(
        db=db,
        organization_id=org_alpha.id,
        data=TicketCreate(
            title="Email calendar sync error",
            description="Outlook mobile sync loop",
            priority="NORMAL",
            category="Email",
            tags=["outlook", "mobile"],
        ),
        requester_user=user_requester_a1,
    )

    # 1. Search by keyword "driver"
    f1 = TicketSearchFilter(query="driver")
    res1 = SearchService.search_tickets(db, org_alpha.id, f1)
    assert len(res1) == 1
    assert res1[0].id == t1.id

    # 2. Search by category "Email"
    f2 = TicketSearchFilter(category="Email")
    res2 = SearchService.search_tickets(db, org_alpha.id, f2)
    assert len(res2) == 1
    assert res2[0].id == t2.id

    # 3. Search by tag "win11"
    f3 = TicketSearchFilter(tag="win11")
    res3 = SearchService.search_tickets(db, org_alpha.id, f3)
    assert len(res3) == 1
    assert res3[0].id == t1.id


def test_knowledge_retrieval_service_bounded_evidence_and_tenant_isolation(
    client, db, org_alpha, org_beta, user_requester_a1, user_agent_a, user_agent_b, auth_agent_a
):
    # Org A: Resolved ticket with knowledge_useful = True
    t_alpha = TicketService.create_ticket(
        db=db,
        organization_id=org_alpha.id,
        data=TicketCreate(
            title="VPN tunnel disconnects every hour",
            description="Client sessions terminate with timeout 504",
            category="Network",
            tags=["vpn", "firewall", "ikev2"],
        ),
        actor_user=user_agent_a,
    )
    ResolutionService.record_resolution(
        db=db,
        ticket=t_alpha,
        data=ResolutionCreate(
            summary="Updated keepalive interval on firewall gateway.",
            root_cause="Phase 2 rekey lifetime mismatch between client and concentrator.",
            resolution_steps="Adjusted lifetime to 28800s and enabled DPD keepalives.",
            verification="admin_verified",
            knowledge_useful=True,
        ),
        actor=user_agent_a,
    )

    # Org B: Similar ticket in Org B
    t_beta = TicketService.create_ticket(
        db=db,
        organization_id=org_beta.id,
        data=TicketCreate(
            title="VPN tunnel disconnects in Beta",
            description="Beta confidential VPN issue",
            category="Network",
        ),
        actor_user=user_agent_b,
    )
    ResolutionService.record_resolution(
        db=db,
        ticket=t_beta,
        data=ResolutionCreate(
            summary="Beta secret resolution",
            resolution_steps="Beta secret steps",
            verification="admin_verified",
            knowledge_useful=True,
        ),
        actor=user_agent_b,
    )

    # Agent A queries knowledge base for "VPN tunnel disconnect"
    evidence = KnowledgeRetrievalService.retrieve_evidence(
        db=db,
        organization_id=org_alpha.id,
        query="VPN tunnel disconnects with timeout",
        category="Network",
        tags=["vpn"],
        limit=5,
    )

    assert len(evidence) >= 1
    # Must retrieve Alpha ticket
    assert any(e.ticket_id == t_alpha.id for e in evidence)
    # MUST NEVER retrieve Beta ticket (tenant isolation strictly preserved!)
    assert not any(e.ticket_id == t_beta.id for e in evidence)

    # Verify structured evidence citations
    item = next(e for e in evidence if e.ticket_id == t_alpha.id)
    assert item.ticket_number == t_alpha.ticket_number
    assert item.summary == "Updated keepalive interval on firewall gateway."
    assert item.relevance_score > 0
    assert "firewall" in item.tags
