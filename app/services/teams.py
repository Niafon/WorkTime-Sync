from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.team import Team
from app.repositories.teams import TeamRepository
from app.schemas.team import TeamCreate, TeamUpdate
from app.services.exceptions import NotFoundError


class TeamService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.teams = TeamRepository(session)

    async def create(self, payload: TeamCreate) -> Team:
        team = await self.teams.create(Team(**payload.model_dump()))
        await self.session.commit()
        return team

    async def list(self) -> list[Team]:
        return await self.teams.list()

    async def get(self, team_id: UUID) -> Team:
        team = await self.teams.get(team_id)
        if team is None:
            raise NotFoundError("team not found")
        return team

    async def update(self, team_id: UUID, payload: TeamUpdate) -> Team:
        team = await self.get(team_id)
        team = await self.teams.update(team, payload.model_dump(exclude_unset=True))
        await self.session.commit()
        return team
