from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.team import Team


class TeamRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, team: Team) -> Team:
        self.session.add(team)
        await self.session.flush()
        await self.session.refresh(team)
        return team

    async def list(self) -> list[Team]:
        result = await self.session.execute(select(Team).order_by(Team.created_at.desc()))
        return list(result.scalars().all())

    async def get(self, team_id: UUID) -> Team | None:
        return await self.session.get(Team, team_id)

    async def update(self, team: Team, values: dict[str, object]) -> Team:
        for field, value in values.items():
            setattr(team, field, value)
        await self.session.flush()
        await self.session.refresh(team)
        return team

    async def delete(self, team: Team) -> None:
        await self.session.delete(team)
        await self.session.flush()
