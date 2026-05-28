from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import (
    NOTIFICATION_STATUS_DEFERRED,
    NOTIFICATION_STATUS_DELIVERED,
    Notification,
)


class NotificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, notification: Notification) -> Notification:
        self.session.add(notification)
        await self.session.flush()
        await self.session.refresh(notification)
        return notification

    async def get(self, notification_id: UUID) -> Notification | None:
        result = await self.session.execute(
            select(Notification).where(Notification.id == notification_id)
        )
        return result.scalar_one_or_none()

    async def list_for_recipient(
        self,
        recipient_id: UUID,
        *,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Notification]:
        stmt = select(Notification).where(Notification.recipient_id == recipient_id)
        if unread_only:
            stmt = stmt.where(Notification.read_at.is_(None))
        stmt = stmt.order_by(Notification.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def mark_as_read(self, notification: Notification) -> Notification:
        if notification.read_at is None:
            notification.read_at = datetime.now(UTC)
            await self.session.flush()
            await self.session.refresh(notification)
        return notification

    async def promote_due_deferred(
        self, recipient_id: UUID, *, now: datetime | None = None
    ) -> int:
        """Lazy-доставка: deferred-уведомления, у которых deferred_until <= now,
        переводим в delivered. Возвращает количество переведённых записей.

        Закрывает разрыв «нет cron/worker'а для отправки отложенных»: пока
        полноценный планировщик не подключён, делаем это при чтении списка.
        """
        timestamp = now or datetime.now(UTC)
        result = await self.session.execute(
            update(Notification)
            .where(
                Notification.recipient_id == recipient_id,
                Notification.status == NOTIFICATION_STATUS_DEFERRED,
                Notification.deferred_until.is_not(None),
                Notification.deferred_until <= timestamp,
            )
            .values(status=NOTIFICATION_STATUS_DELIVERED, deferred_until=None)
        )
        await self.session.flush()
        return result.rowcount or 0
