from __future__ import annotations

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.team import Team
from app.models.team_member import TeamMember
from app.repositories.employees import EmployeeRepository
from app.repositories.team_members import TeamMemberRepository
from app.repositories.teams import TeamRepository
from app.schemas.team import TeamCreate, TeamUpdate
from app.services.exceptions import InvalidOperationError, NotFoundError


class TeamService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.teams = TeamRepository(session)
        self.team_members = TeamMemberRepository(session)
        self.employees = EmployeeRepository(session)

    async def create(self, payload: TeamCreate) -> Team:
        # Команду и её участников создаём в одной транзакции, чтобы не оставлять
        # «голые» команды без состава при ошибке на полпути.
        for member in payload.members:
            if await self.employees.get(member.employee_id) is None:
                raise NotFoundError(f"employee {member.employee_id} not found")

        team = Team(
            name=payload.name,
            description=payload.description,
            avatar_url=payload.avatar_url,
        )
        team = await self.teams.create(team)

        for member in payload.members:
            self.session.add(
                TeamMember(
                    team_id=team.id,
                    employee_id=member.employee_id,
                    role_in_team=member.role_in_team,
                )
            )

        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise InvalidOperationError("duplicate employee in members list") from exc

        await self.session.refresh(team)
        return team

    async def list(self, *, skip: int = 0, limit: int | None = None) -> list[Team]:
        return await self.teams.list(skip=skip, limit=limit)

    async def list_with_counts(
        self, *, skip: int = 0, limit: int | None = None
    ) -> list[tuple[Team, int]]:
        teams = await self.teams.list(skip=skip, limit=limit)
        counts = await self.team_members.counts_by_team([t.id for t in teams])
        return [(t, counts.get(t.id, 0)) for t in teams]

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

    async def delete(self, team_id: UUID) -> None:
        team = await self.get(team_id)
        await self.teams.delete(team)
        await self.session.commit()
