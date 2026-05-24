from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TeamMemberCreate(BaseModel):
    team_id: UUID
    employee_id: UUID
    role_in_team: str


class TeamMemberResponse(BaseModel):
    team_id: UUID
    employee_id: UUID
    role_in_team: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
