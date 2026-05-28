from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.employee import Employee
    from app.models.roadmap_item import RoadmapItem


NOTIFICATION_TYPE_ROADMAP_REQUEST = "roadmap_actualization_request"
NOTIFICATION_TYPE_ROADMAP_STATUS_CHANGED = "roadmap_status_changed"
NOTIFICATION_TYPE_RESCHEDULE_PROPOSAL = "reschedule_proposal"


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    recipient_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
    )
    type: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    related_roadmap_item_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("roadmap_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    recipient: Mapped["Employee"] = relationship(
        "Employee",
        back_populates="notifications",
        foreign_keys=[recipient_id],
    )
    related_roadmap_item: Mapped["RoadmapItem | None"] = relationship(
        "RoadmapItem",
        back_populates="notifications",
        foreign_keys=[related_roadmap_item_id],
    )

    __table_args__ = (
        Index("ix_notifications_recipient_id", "recipient_id"),
    )
