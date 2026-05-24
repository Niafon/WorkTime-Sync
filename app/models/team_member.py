from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.employee import Employee
    from app.models.team import Team


class TeamMember(Base):
    __tablename__ = "team_members"
    __table_args__ = (
        Index("ix_team_members_team_id", "team_id"),
        Index("ix_team_members_employee_id", "employee_id"),
    )

    team_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("teams.id"),
        primary_key=True,
    )
    employee_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("employees.id"),
        primary_key=True,
    )
    role_in_team: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    team: Mapped[Team] = relationship("Team", back_populates="members")
    employee: Mapped[Employee] = relationship("Employee", back_populates="team_members")
