from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.employee import Employee
    from app.models.notification import Notification
    from app.models.schedule_confirmation_request import ScheduleConfirmationRequest
    from app.models.team import Team


ROADMAP_SUBJECT_EMPLOYEE = "employee"
ROADMAP_SUBJECT_TEAM = "team"

ROADMAP_STATUS_PENDING = "pending"
ROADMAP_STATUS_REQUESTED = "requested"
ROADMAP_STATUS_ACKNOWLEDGED = "acknowledged"
ROADMAP_STATUS_UPDATED = "updated"
ROADMAP_STATUS_COMPLETED = "completed"
ROADMAP_STATUS_DEFERRED = "deferred"
ROADMAP_STATUS_IGNORED = "ignored"
ROADMAP_STATUS_DISMISSED = "dismissed"

ROADMAP_OPEN_STATUSES: frozenset[str] = frozenset(
    {
        ROADMAP_STATUS_PENDING,
        ROADMAP_STATUS_REQUESTED,
        ROADMAP_STATUS_ACKNOWLEDGED,
        ROADMAP_STATUS_UPDATED,
        ROADMAP_STATUS_DEFERRED,
    }
)
ROADMAP_TERMINAL_STATUSES: frozenset[str] = frozenset(
    {
        ROADMAP_STATUS_COMPLETED,
        ROADMAP_STATUS_IGNORED,
        ROADMAP_STATUS_DISMISSED,
    }
)

ROADMAP_OPEN_STATUSES_SQL = (
    "('pending','requested','acknowledged','updated','deferred')"
)


class RoadmapItem(Base):
    __tablename__ = "roadmap_items"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    subject_type: Mapped[str] = mapped_column(String(20), nullable=False)
    subject_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    employee_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=True,
    )
    team_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=True,
    )
    recommendation_code: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    priority_score: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    assigned_to_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_by_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="SET NULL"),
        nullable=True,
    )
    confirmation_request_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("schedule_confirmation_requests.id", ondelete="SET NULL"),
        nullable=True,
    )
    metric_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    employee: Mapped["Employee | None"] = relationship(
        "Employee",
        foreign_keys=[employee_id],
        back_populates="roadmap_items",
    )
    team: Mapped["Team | None"] = relationship(
        "Team",
        foreign_keys=[team_id],
        back_populates="roadmap_items",
    )
    assigned_to: Mapped["Employee | None"] = relationship(
        "Employee",
        foreign_keys=[assigned_to_id],
    )
    created_by: Mapped["Employee | None"] = relationship(
        "Employee",
        foreign_keys=[created_by_id],
    )
    confirmation_request: Mapped["ScheduleConfirmationRequest | None"] = relationship(
        "ScheduleConfirmationRequest",
        foreign_keys=[confirmation_request_id],
    )
    notifications: Mapped[list["Notification"]] = relationship(
        "Notification",
        back_populates="related_roadmap_item",
        foreign_keys="Notification.related_roadmap_item_id",
    )

    __table_args__ = (
        Index("ix_roadmap_items_subject", "subject_type", "subject_id"),
        Index("ix_roadmap_items_status", "status"),
        Index("ix_roadmap_items_priority", "priority_score"),
        Index("ix_roadmap_items_employee_id", "employee_id"),
        Index("ix_roadmap_items_team_id", "team_id"),
        Index("ix_roadmap_items_assigned_to_id", "assigned_to_id"),
    )
