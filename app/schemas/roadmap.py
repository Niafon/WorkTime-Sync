from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.analytics.roadmap_priority import CODE_TITLE_RU
from app.models.roadmap_item import RoadmapItem

RoadmapSubjectLiteral = Literal["employee", "team"]
RoadmapSeverityLiteral = Literal["critical", "high", "medium", "low"]
RoadmapStatusLiteral = Literal[
    "pending",
    "requested",
    "acknowledged",
    "updated",
    "completed",
    "deferred",
    "ignored",
    "dismissed",
]


class RoadmapItemResponse(BaseModel):
    id: UUID
    subject_type: RoadmapSubjectLiteral
    subject_id: UUID
    employee_id: UUID | None = None
    team_id: UUID | None = None
    recommendation_code: str
    title: str
    severity: RoadmapSeverityLiteral
    reason: str
    action: str
    priority_score: float
    status: RoadmapStatusLiteral
    notes: str | None = None
    due_at: datetime | None = None
    requested_at: datetime | None = None
    acknowledged_at: datetime | None = None
    completed_at: datetime | None = None
    assigned_to_id: UUID | None = None
    created_by_id: UUID | None = None
    confirmation_request_id: UUID | None = None
    metric_snapshot: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime
    subject_name: str | None = None
    subject_avatar_url: str | None = None

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_item(cls, item: RoadmapItem) -> "RoadmapItemResponse":
        subject_name: str | None = None
        subject_avatar_url: str | None = None
        if item.subject_type == "employee" and item.employee is not None:
            subject_name = item.employee.full_name
        elif item.subject_type == "team" and item.team is not None:
            subject_name = item.team.name
            subject_avatar_url = item.team.avatar_url
        return cls(
            id=item.id,
            subject_type=item.subject_type,  # type: ignore[arg-type]
            subject_id=item.subject_id,
            employee_id=item.employee_id,
            team_id=item.team_id,
            recommendation_code=item.recommendation_code,
            title=CODE_TITLE_RU.get(
                item.recommendation_code, item.recommendation_code
            ),
            severity=item.severity,  # type: ignore[arg-type]
            reason=item.reason,
            action=item.action,
            priority_score=item.priority_score,
            status=item.status,  # type: ignore[arg-type]
            notes=item.notes,
            due_at=item.due_at,
            requested_at=item.requested_at,
            acknowledged_at=item.acknowledged_at,
            completed_at=item.completed_at,
            assigned_to_id=item.assigned_to_id,
            created_by_id=item.created_by_id,
            confirmation_request_id=item.confirmation_request_id,
            metric_snapshot=item.metric_snapshot,
            created_at=item.created_at,
            updated_at=item.updated_at,
            subject_name=subject_name,
            subject_avatar_url=subject_avatar_url,
        )


class RoadmapStatusUpdateRequest(BaseModel):
    status: RoadmapStatusLiteral
    notes: str | None = None


class RoadmapItemUpdateRequest(BaseModel):
    notes: str | None = None
    assigned_to_id: UUID | None = None
    due_at: datetime | None = None


class RoadmapGenerateRequestBody(BaseModel):
    team_id: UUID | None = None
    employee_id: UUID | None = None


class RoadmapGenerateResponse(BaseModel):
    created: int = Field(ge=0)
    skipped: int = Field(ge=0)
    items: list[RoadmapItemResponse]


class RoadmapListResponse(BaseModel):
    items: list[RoadmapItemResponse]
    total: int
    counts_by_status: dict[str, int]
    counts_by_severity: dict[str, int]


class RoadmapRecomputeResponse(BaseModel):
    updated: int
