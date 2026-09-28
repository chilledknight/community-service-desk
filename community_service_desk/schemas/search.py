"""Search and Knowledge Retrieval schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class TicketSearchFilter(BaseModel):
    ticket_number: str | None = None
    query: str | None = Field(
        None, description="Text search across title, description, and resolution content"
    )
    requester: str | None = Field(None, description="Requester email or name")
    status: str | None = None
    priority: str | None = None
    queue_id: str | None = None
    assigned_agent_id: str | None = None
    category: str | None = None
    tag: str | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None
    resolved_after: datetime | None = None
    resolved_before: datetime | None = None
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class KnowledgeSearchQuery(BaseModel):
    query: str = Field(..., min_length=2, description="Problem description or search keywords")
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    limit: int = Field(default=5, ge=1, le=20)


class KnowledgeEvidence(BaseModel):
    """Structured evidence item returned by KnowledgeRetrievalService."""

    ticket_id: str
    ticket_number: str
    title: str
    category: str | None = None
    tags: list[str] = []
    resolution_id: str
    summary: str
    root_cause: str | None = None
    resolution_steps: str
    verification: str
    resolved_at: datetime
    resolved_by_name: str
    relevance_score: float = Field(..., description="Deterministic keyword and tag relevance score")
