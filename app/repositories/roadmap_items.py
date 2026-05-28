from __future__ import annotations

import builtins
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.roadmap_item import (
    ROADMAP_OPEN_STATUSES,
    ROADMAP_STATUS_DISMISSED,
    RoadmapItem,
)
from app.models.team_member import TeamMember


class RoadmapItemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, item: RoadmapItem) -> RoadmapItem:
        self.session.add(item)
        await self.session.flush()
        await self.session.refresh(item)
        return item

    async def bulk_create(
        self, items: builtins.list[RoadmapItem]
    ) -> builtins.list[RoadmapItem]:
        if not items:
            return []
        self.session.add_all(items)
        await self.session.flush()
        return items

    async def get(
        self, item_id: UUID, *, with_relations: bool = True
    ) -> RoadmapItem | None:
        stmt = select(RoadmapItem).where(RoadmapItem.id == item_id)
        if with_relations:
            stmt = stmt.options(
                selectinload(RoadmapItem.employee),
                selectinload(RoadmapItem.team),
                selectinload(RoadmapItem.assigned_to),
                selectinload(RoadmapItem.confirmation_request),
            )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    def _apply_filters(
        self,
        stmt,
        *,
        statuses: builtins.list[str] | None,
        severities: builtins.list[str] | None,
        subject_type: str | None,
        team_id: UUID | None,
        employee_id: UUID | None,
        assigned_to_id: UUID | None,
        search: str | None,
        include_closed: bool,
    ):
        if statuses:
            stmt = stmt.where(RoadmapItem.status.in_(statuses))
        elif not include_closed:
            stmt = stmt.where(RoadmapItem.status.in_(tuple(ROADMAP_OPEN_STATUSES)))
        if severities:
            stmt = stmt.where(RoadmapItem.severity.in_(severities))
        if subject_type is not None:
            stmt = stmt.where(RoadmapItem.subject_type == subject_type)
        if team_id is not None:
            members_subq = select(TeamMember.employee_id).where(
                TeamMember.team_id == team_id
            )
            stmt = stmt.where(
                or_(
                    RoadmapItem.team_id == team_id,
                    RoadmapItem.employee_id.in_(members_subq),
                )
            )
        if employee_id is not None:
            stmt = stmt.where(RoadmapItem.employee_id == employee_id)
        if assigned_to_id is not None:
            stmt = stmt.where(RoadmapItem.assigned_to_id == assigned_to_id)
        if search:
            pattern = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    RoadmapItem.reason.ilike(pattern),
                    RoadmapItem.action.ilike(pattern),
                )
            )
        return stmt

    async def list(
        self,
        *,
        statuses: builtins.list[str] | None = None,
        severities: builtins.list[str] | None = None,
        subject_type: str | None = None,
        team_id: UUID | None = None,
        employee_id: UUID | None = None,
        assigned_to_id: UUID | None = None,
        search: str | None = None,
        include_closed: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> builtins.list[RoadmapItem]:
        stmt = select(RoadmapItem).options(
            selectinload(RoadmapItem.employee),
            selectinload(RoadmapItem.team),
            selectinload(RoadmapItem.assigned_to),
            selectinload(RoadmapItem.confirmation_request),
        )
        stmt = self._apply_filters(
            stmt,
            statuses=statuses,
            severities=severities,
            subject_type=subject_type,
            team_id=team_id,
            employee_id=employee_id,
            assigned_to_id=assigned_to_id,
            search=search,
            include_closed=include_closed,
        )
        stmt = stmt.order_by(
            RoadmapItem.priority_score.desc(), RoadmapItem.created_at.desc()
        ).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all())

    async def count(
        self,
        *,
        statuses: builtins.list[str] | None = None,
        severities: builtins.list[str] | None = None,
        subject_type: str | None = None,
        team_id: UUID | None = None,
        employee_id: UUID | None = None,
        assigned_to_id: UUID | None = None,
        search: str | None = None,
        include_closed: bool = False,
    ) -> int:
        stmt = select(func.count()).select_from(RoadmapItem)
        stmt = self._apply_filters(
            stmt,
            statuses=statuses,
            severities=severities,
            subject_type=subject_type,
            team_id=team_id,
            employee_id=employee_id,
            assigned_to_id=assigned_to_id,
            search=search,
            include_closed=include_closed,
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one())

    async def list_open_for_subjects(
        self, pairs: builtins.list[tuple[str, UUID]]
    ) -> builtins.list[RoadmapItem]:
        if not pairs:
            return []
        subject_ids = list({pair[1] for pair in pairs})
        subject_types = list({pair[0] for pair in pairs})
        stmt = (
            select(RoadmapItem)
            .where(
                RoadmapItem.status.in_(tuple(ROADMAP_OPEN_STATUSES)),
                RoadmapItem.subject_type.in_(subject_types),
                RoadmapItem.subject_id.in_(subject_ids),
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_open_by_recommendation(
        self,
        *,
        subject_type: str,
        subject_id: UUID,
        recommendation_code: str,
    ) -> RoadmapItem | None:
        """Самый свежий open-item по композитному ключу рекомендации."""
        result = await self.session.execute(
            select(RoadmapItem)
            .where(
                RoadmapItem.status.in_(tuple(ROADMAP_OPEN_STATUSES)),
                RoadmapItem.subject_type == subject_type,
                RoadmapItem.subject_id == subject_id,
                RoadmapItem.recommendation_code == recommendation_code,
            )
            .order_by(RoadmapItem.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_all_open(self) -> builtins.list[RoadmapItem]:
        result = await self.session.execute(
            select(RoadmapItem).where(
                RoadmapItem.status.in_(tuple(ROADMAP_OPEN_STATUSES))
            )
        )
        return list(result.scalars().all())

    async def update(
        self, item: RoadmapItem, values: dict[str, Any]
    ) -> RoadmapItem:
        for field, value in values.items():
            setattr(item, field, value)
        await self.session.flush()
        await self.session.refresh(item)
        return item

    async def delete(self, item: RoadmapItem) -> None:
        await self.session.delete(item)
        await self.session.flush()

    async def aggregate_status_counts(
        self,
        *,
        team_id: UUID | None = None,
        include_closed: bool = True,
    ) -> dict[str, int]:
        stmt = select(RoadmapItem.status, func.count()).group_by(RoadmapItem.status)
        if team_id is not None:
            members_subq = select(TeamMember.employee_id).where(
                TeamMember.team_id == team_id
            )
            stmt = stmt.where(
                or_(
                    RoadmapItem.team_id == team_id,
                    RoadmapItem.employee_id.in_(members_subq),
                )
            )
        if not include_closed:
            stmt = stmt.where(RoadmapItem.status != ROADMAP_STATUS_DISMISSED)
        result = await self.session.execute(stmt)
        return {status: int(count) for status, count in result.all()}

    async def aggregate_severity_counts(
        self,
        *,
        team_id: UUID | None = None,
        include_closed: bool = False,
    ) -> dict[str, int]:
        stmt = select(RoadmapItem.severity, func.count()).group_by(
            RoadmapItem.severity
        )
        if team_id is not None:
            members_subq = select(TeamMember.employee_id).where(
                TeamMember.team_id == team_id
            )
            stmt = stmt.where(
                or_(
                    RoadmapItem.team_id == team_id,
                    RoadmapItem.employee_id.in_(members_subq),
                )
            )
        if not include_closed:
            stmt = stmt.where(RoadmapItem.status.in_(tuple(ROADMAP_OPEN_STATUSES)))
        result = await self.session.execute(stmt)
        return {severity: int(count) for severity, count in result.all()}
