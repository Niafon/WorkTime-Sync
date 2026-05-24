from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.activity_event import ActivityEvent
    from app.models.employee_metric import EmployeeMetric
    from app.models.schedule_exception import ScheduleException
    from app.models.team_member import TeamMember
    from app.models.work_schedule import WorkSchedule


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    vk_user_id: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    role: Mapped[str] = mapped_column(String(40), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    position: Mapped[str | None] = mapped_column(String(150), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    work_format: Mapped[str] = mapped_column(String(30), nullable=False)
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

    team_members: Mapped[list[TeamMember]] = relationship(
        "TeamMember",
        back_populates="employee",
        cascade="all, delete-orphan",
    )
    work_schedules: Mapped[list[WorkSchedule]] = relationship(
        "WorkSchedule",
        back_populates="employee",
        cascade="all, delete-orphan",
    )
    schedule_exceptions: Mapped[list[ScheduleException]] = relationship(
        "ScheduleException",
        back_populates="employee",
        cascade="all, delete-orphan",
    )
    activity_events: Mapped[list[ActivityEvent]] = relationship(
        "ActivityEvent",
        back_populates="employee",
        cascade="all, delete-orphan",
    )
    metrics: Mapped[EmployeeMetric | None] = relationship(
        "EmployeeMetric",
        back_populates="employee",
        cascade="all, delete-orphan",
        uselist=False,
    )
