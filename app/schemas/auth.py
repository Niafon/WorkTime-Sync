from pydantic import BaseModel

from app.schemas.employee import EmployeeResponse


class VKLoginResponse(BaseModel):
    authorization_url: str


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    employee: EmployeeResponse
