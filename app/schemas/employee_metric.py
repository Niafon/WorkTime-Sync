from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class EmployeeMetricResponse(BaseModel):
    id: UUID
    employee_id: UUID
    calculated_at: datetime
    days_since_update: int
    actuality_score: float
    outside_events_count: int
    total_events_count: int
    conflict_rate: float
    load_level: float
    risk_score: float
    risk_level: str

    model_config = ConfigDict(from_attributes=True)
