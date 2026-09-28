"""Ticket event history schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class EventHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    ticket_id: str
    actor_id: str | None = None
    actor_name: str
    actor_type: str
    event_type: str
    old_value: str | None = None
    new_value: str | None = None
    details: dict[str, Any] | None = None
    created_at: datetime
