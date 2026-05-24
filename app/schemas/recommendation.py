from uuid import UUID

from pydantic import BaseModel


class RecommendationResponse(BaseModel):
    code: str
    reason: str
    severity: str
    action: str
    subject_type: str
    subject_id: UUID
