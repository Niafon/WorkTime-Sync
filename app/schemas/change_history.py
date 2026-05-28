from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ChangeHistoryResponse(BaseModel):
    id: UUID
    entity_type: str
    entity_id: UUID
    employee_id: UUID
    action: str
    changed_by: UUID
    changed_at: datetime
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    reason: str | None

    model_config = ConfigDict(from_attributes=True)
