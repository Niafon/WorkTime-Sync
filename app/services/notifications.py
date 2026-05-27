from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.roadmap_priority import CODE_TITLE_RU
from app.core.roles import EmployeeRole
from app.models.employee import Employee
from app.models.notification import (
    NOTIFICATION_TYPE_ROADMAP_REQUEST,
    Notification,
)
from app.models.roadmap_item import (
    ROADMAP_SUBJECT_EMPLOYEE,
    ROADMAP_SUBJECT_TEAM,
    RoadmapItem,
)
from app.repositories.employees import EmployeeRepository
from app.repositories.notifications import NotificationRepository
from app.repositories.team_members import TeamMemberRepository
from app.services.exceptions import InvalidOperationError, NotFoundError


_TEAM_RECIPIENT_ROLES: frozenset[EmployeeRole] = frozenset(
    {EmployeeRole.MANAGER, EmployeeRole.PM, EmployeeRole.HR}
)


class NotificationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = NotificationRepository(session)
        self.employees = EmployeeRepository(session)
        self.team_members = TeamMemberRepository(session)

    async def create_for_roadmap_request(
        self, item: RoadmapItem, actor: Employee
    ) -> list[Notification]:
        recipients = await self._resolve_recipients(item)
        created: list[Notification] = []
        title = self._title_for(item)
        payload = {
            "roadmap_item_id": str(item.id),
            "recommendation_code": item.recommendation_code,
            "severity": item.severity,
            "requested_by": str(actor.id),
        }
        for recipient in recipients:
            notification = Notification(
                recipient_id=recipient.id,
                type=NOTIFICATION_TYPE_ROADMAP_REQUEST,
                title=title,
                body=item.action,
                payload=payload,
                related_roadmap_item_id=item.id,
            )
            created.append(await self.repo.create(notification))
        return created

    async def list_for_recipient(
        self,
        recipient_id: UUID,
        *,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Notification]:
        return await self.repo.list_for_recipient(
            recipient_id, unread_only=unread_only, limit=limit, offset=offset
        )

    async def mark_as_read(
        self, notification_id: UUID, actor: Employee
    ) -> Notification:
        notification = await self.repo.get(notification_id)
        if notification is None:
            raise NotFoundError("notification not found")
        if notification.recipient_id != actor.id and actor.role != EmployeeRole.ADMIN:
            raise InvalidOperationError("cannot read others' notifications")
        notification = await self.repo.mark_as_read(notification)
        await self.session.commit()
        return notification

    async def _resolve_recipients(self, item: RoadmapItem) -> list[Employee]:
        if item.subject_type == ROADMAP_SUBJECT_EMPLOYEE and item.employee_id:
            employee = await self.employees.get(item.employee_id)
            return [employee] if employee else []
        if item.subject_type == ROADMAP_SUBJECT_TEAM and item.team_id:
            employee_ids = await self.team_members.list_employee_ids_for_team(
                item.team_id
            )
            employees = await self.employees.list_by_ids(employee_ids)
            return [
                emp
                for emp in employees
                if emp.role in _TEAM_RECIPIENT_ROLES
            ]
        return []

    @staticmethod
    def _title_for(item: RoadmapItem) -> str:
        label = CODE_TITLE_RU.get(item.recommendation_code, item.recommendation_code)
        return f"Запрос актуализации: {label}"
