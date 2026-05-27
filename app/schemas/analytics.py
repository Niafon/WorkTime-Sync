from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class ActualityHistoryPoint(BaseModel):
    month: str
    value: float


class RiskDistributionPoint(BaseModel):
    month: str
    low: int = 0
    medium: int = 0
    high: int = 0
    critical: int = 0


class TeamRatingItem(BaseModel):
    team_id: UUID
    name: str
    members_count: int
    avg_actuality: float
    avg_risk_score: float
    attention_count: int


class SummaryDeltasResponse(BaseModel):
    period: Literal["month", "week"]
    ai_delta: float
    ci_delta: float
    outdated_schedules_delta: int


class TeamMetricsHistoryPoint(BaseModel):
    month: str
    avg_actuality: float
    avg_risk_score: float
    attention_count: int
