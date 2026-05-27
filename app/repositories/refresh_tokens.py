from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.refresh_token import RefreshToken


class RefreshTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        employee_id: UUID,
        jti: str,
        issued_at: datetime,
        expires_at: datetime,
    ) -> RefreshToken:
        token = RefreshToken(
            employee_id=employee_id,
            jti=jti,
            issued_at=issued_at,
            expires_at=expires_at,
        )
        self.session.add(token)
        await self.session.flush()
        await self.session.refresh(token)
        return token

    async def get_by_jti(self, jti: str) -> RefreshToken | None:
        result = await self.session.execute(select(RefreshToken).where(RefreshToken.jti == jti))
        return result.scalar_one_or_none()

    async def mark_revoked(
        self,
        token: RefreshToken,
        *,
        replaced_by_jti: str | None = None,
    ) -> None:
        token.revoked_at = datetime.now(UTC)
        token.replaced_by_jti = replaced_by_jti
        await self.session.flush()

    async def revoke_all_for_employee(self, employee_id: UUID) -> int:
        """Массовый отзыв — для reuse-detection и опционального logout-everywhere.

        Возвращает количество затронутых записей. Уже отозванные пропускаются.
        """
        now = datetime.now(UTC)
        stmt = (
            update(RefreshToken)
            .where(RefreshToken.employee_id == employee_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        result = await self.session.execute(stmt)
        return result.rowcount or 0
