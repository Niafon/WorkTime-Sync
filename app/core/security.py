from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID

from jose import JWTError, jwt  # type: ignore[import-untyped]
from pydantic import BaseModel, ValidationError

from app.core.config import settings


class TokenPayload(BaseModel):
    employee_id: UUID
    role: str
    exp: datetime


def create_access_token(
    *,
    employee_id: UUID,
    role: str,
    expires_delta: timedelta | None = None,
) -> str:
    expires_at = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )
    payload = {
        "employee_id": str(employee_id),
        "role": role,
        "exp": expires_at,
    }
    return cast(str, jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm))


def decode_access_token(token: str) -> TokenPayload:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return TokenPayload.model_validate(payload)
    except (JWTError, ValidationError) as exc:
        raise ValueError("invalid access token") from exc
