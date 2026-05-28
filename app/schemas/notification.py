from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class NotificationResponse(BaseModel):
    id: UUID
    recipient_id: UUID
    type: str
    title: str
    body: str
    payload: dict[str, Any] | None = None
    related_roadmap_item_id: UUID | None = None
    read_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
