from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.employee import Employee


CONFIRMATION_STATUS_PENDING = "pending"
CONFIRMATION_STATUS_CONFIRMED = "confirmed"
CONFIRMATION_STATUS_DECLINED = "declined"


class ScheduleConfirmationRequest(Base):
    __tablename__ = "schedule_confirmation_requests"

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
    requested_by_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("employees.id"),
        nullable=True,
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    response_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    employee: Mapped[Employee] = relationship(
        "Employee",
        back_populates="confirmation_requests",
        foreign_keys="ScheduleConfirmationRequest.employee_id",
    )
    requested_by: Mapped[Employee | None] = relationship(
        "Employee",
        back_populates="confirmation_requests_made",
        foreign_keys="ScheduleConfirmationRequest.requested_by_id",
    )
