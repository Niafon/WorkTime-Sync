from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class EmployeeMetricSnapshot(Base):
    """Append-only снимок EmployeeMetric для timeseries-аналитики (ТЗ §14)."""

    __tablename__ = "employee_metric_snapshots"
    __table_args__ = (
        Index("ix_employee_metric_snapshots_employee_taken", "employee_id", "taken_at"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    employee_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("employees.id"),
        index=True,
        nullable=False,
    )
    taken_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
        nullable=False,
    )
    days_since_update: Mapped[int] = mapped_column(nullable=False)
    actuality_score: Mapped[float] = mapped_column(nullable=False)
    outside_events_count: Mapped[int] = mapped_column(nullable=False)
    total_events_count: Mapped[int] = mapped_column(nullable=False)
    conflict_rate: Mapped[float] = mapped_column(nullable=False)
    load_level: Mapped[float] = mapped_column(nullable=False)
    zone_factor: Mapped[float] = mapped_column(nullable=False)
    hr_factor: Mapped[float] = mapped_column(nullable=False)
    risk_score: Mapped[float] = mapped_column(nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False)
