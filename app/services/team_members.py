from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.team_member import TeamMember
from app.repositories.employees import EmployeeRepository
from app.repositories.team_members import TeamMemberRepository
from app.repositories.teams import TeamRepository
from app.schemas.team_member import TeamMemberCreate
from app.services.exceptions import InvalidOperationError, NotFoundError


class TeamMemberService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.employees = EmployeeRepository(session)
        self.teams = TeamRepository(session)
        self.team_members = TeamMemberRepository(session)

    async def create(self, team_id: UUID, payload: TeamMemberCreate) -> TeamMember:
        if payload.team_id != team_id:
            raise InvalidOperationError("team_id in path and body must match")
        if await self.teams.get(team_id) is None:
            raise NotFoundError("team not found")
        if await self.employees.get(payload.employee_id) is None:
            raise NotFoundError("employee not found")

        team_member = TeamMember(**payload.model_dump())
        try:
            team_member = await self.team_members.create(team_member)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise InvalidOperationError("employee is already a member of this team") from exc
        return team_member

    async def delete(self, team_id: UUID, employee_id: UUID) -> None:
        if await self.teams.get(team_id) is None:
            raise NotFoundError("team not found")
        team_member = await self.team_members.get(team_id, employee_id)
        if team_member is None:
            raise NotFoundError("team member not found")

        await self.team_members.delete(team_member)
        await self.session.commit()
