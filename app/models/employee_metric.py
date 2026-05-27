from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.employee import Employee


class EmployeeMetric(Base):
    __tablename__ = "employee_metrics"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    employee_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("employees.id"),
        index=True,
        unique=True,
        nullable=False,
    )
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    days_since_update: Mapped[int] = mapped_column(nullable=False)
    actuality_score: Mapped[float] = mapped_column(nullable=False)
    outside_events_count: Mapped[int] = mapped_column(nullable=False)
    total_events_count: Mapped[int] = mapped_column(nullable=False)
    conflict_rate: Mapped[float] = mapped_column(nullable=False)
    load_level: Mapped[float] = mapped_column(nullable=False)
    zone_factor: Mapped[float] = mapped_column(nullable=False, default=0.0, server_default="0")
    hr_factor: Mapped[float] = mapped_column(nullable=False, default=0.0, server_default="0")
    risk_score: Mapped[float] = mapped_column(nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False)

    employee: Mapped[Employee] = relationship("Employee", back_populates="metrics")
