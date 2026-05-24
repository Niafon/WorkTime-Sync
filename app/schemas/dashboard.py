from datetime import datetime

from pydantic import BaseModel


class DashboardSummaryResponse(BaseModel):
    total_employees: int
    total_teams: int
    employees_by_risk_level: dict[str, int]
    overloaded_employees_count: int
    outdated_schedules_count: int
    outside_schedule_events_count: int
    last_calculation_at: datetime | None
