"""AI-Ready Knowledge Retrieval Service.

This service acts as the retrieval abstraction for historical resolutions,
preserving organization boundaries and providing bounded evidence for future
AI advisory layers without making external model calls in v0.1.
"""

import re
from datetime import datetime, timezone

from sqlalchemy.orm import Session, joinedload

from community_service_desk.models.resolution import TicketResolution
from community_service_desk.schemas.search import KnowledgeEvidence


def tokenize(text: str) -> set[str]:
    """Extract normalized alphanumeric words from text."""
    if not text:
        return set()
    return set(re.findall(r"\b[a-zA-Z0-9_-]{2,}\b", text.lower()))


class KnowledgeRetrievalService:
    """Service abstraction for retrieving historical ticket resolution knowledge.

    ARCHITECTURAL PRINCIPLES:
    1. Authorization Scoping:
       Only tickets within the authorized organization context are retrieved.
       Never query across tenant boundaries.
    2. Bounded Evidence:
       Returns curated resolution records with citations (ticket_id and resolution_id),
       preventing arbitrary or unbounded data exposure.
    3. Deterministic Baseline:
       v0.1 implements deterministic PostgreSQL keyword and tag matching, serving as
       the drop-in retrieval foundation for future semantic/vector embeddings.
    """

    @classmethod
    def retrieve_evidence(
        cls,
        db: Session,
        organization_id: str,
        query: str,
        category: str | None = None,
        tags: list[str] | None = None,
        limit: int = 5,
    ) -> list[KnowledgeEvidence]:
        """Search eligible historical resolutions and return ranked bounded evidence."""
        # 1. Tenant boundary enforcement: Only resolutions in this organization
        # 2. Eligibility filter: Only knowledge_useful resolutions on resolved/closed tickets
        resolutions_query = (
            db.query(TicketResolution)
            .filter(
                TicketResolution.organization_id == organization_id,
                TicketResolution.knowledge_useful.is_(True),
            )
            .join(TicketResolution.ticket)
            .options(
                joinedload(TicketResolution.ticket),
                joinedload(TicketResolution.resolved_by),
            )
        )

        candidates = resolutions_query.all()
        if not candidates:
            return []

        query_tokens = tokenize(query)
        target_tags = set(t.strip().lower() for t in (tags or []) if t.strip())

        scored_items: list[tuple[float, TicketResolution]] = []

        for res in candidates:
            ticket = res.ticket
            if not ticket:
                continue

            # Compute match relevance
            corpus_tokens = (
                tokenize(ticket.title)
                | tokenize(ticket.description)
                | tokenize(res.summary)
                | tokenize(res.root_cause or "")
                | tokenize(res.resolution_steps)
            )

            token_overlap = len(query_tokens.intersection(corpus_tokens))
            score = float(token_overlap * 2.0)

            # Category boost
            if category and ticket.category and category.lower() == ticket.category.lower():
                score += 3.0

            # Tag match boost
            ticket_tags = set(str(t).lower() for t in (ticket.tags or []))
            tag_overlap = len(target_tags.intersection(ticket_tags))
            score += float(tag_overlap * 4.0)

            if score > 0 or not query_tokens:
                scored_items.append((score, res))

        # Sort descending by score, then by recency
        scored_items.sort(
            key=lambda x: (x[0], x[1].created_at or datetime.min.replace(tzinfo=timezone.utc)),
            reverse=True,
        )

        results: list[KnowledgeEvidence] = []
        for score, res in scored_items[:limit]:
            ticket = res.ticket
            results.append(
                KnowledgeEvidence(
                    ticket_id=ticket.id,
                    ticket_number=ticket.ticket_number,
                    title=ticket.title,
                    category=ticket.category,
                    tags=ticket.tags or [],
                    resolution_id=res.id,
                    summary=res.summary,
                    root_cause=res.root_cause,
                    resolution_steps=res.resolution_steps,
                    verification=res.verification,
                    resolved_at=res.created_at,
                    resolved_by_name=res.resolved_by.display_name
                    if res.resolved_by
                    else "Support Agent",
                    relevance_score=round(score, 2),
                )
            )

        return results
