from datetime import UTC, datetime, timedelta
from typing import Literal, cast
from uuid import UUID

from jose import JWTError, jwt  # type: ignore[import-untyped]
from pydantic import BaseModel, ValidationError

from app.core.config import settings

ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"


class TokenPayload(BaseModel):
    employee_id: UUID
    role: str
    exp: datetime
    token_type: Literal["access"] = "access"


class RefreshTokenPayload(BaseModel):
    employee_id: UUID
    jti: str
    token_type: Literal["refresh"]
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
        "token_type": ACCESS_TOKEN_TYPE,
        "exp": expires_at,
    }
    return cast(str, jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm))


def decode_access_token(token: str) -> TokenPayload:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        parsed = TokenPayload.model_validate(payload)
    except (JWTError, ValidationError) as exc:
        raise ValueError("invalid access token") from exc
    if parsed.token_type != ACCESS_TOKEN_TYPE:
        raise ValueError("token is not an access token")
    return parsed


def create_refresh_token(
    *,
    employee_id: UUID,
    jti: str,
    expires_delta: timedelta | None = None,
) -> tuple[str, datetime]:
    """Возвращает (jwt, expires_at) — expires_at нужен для записи в БД и cookie."""
    expires_at = datetime.now(UTC) + (
        expires_delta or timedelta(days=settings.jwt_refresh_token_expire_days)
    )
    payload = {
        "employee_id": str(employee_id),
        "jti": jti,
        "token_type": REFRESH_TOKEN_TYPE,
        "exp": expires_at,
    }
    token = cast(
        str, jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    )
    return token, expires_at


def decode_refresh_token(token: str) -> RefreshTokenPayload:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        parsed = RefreshTokenPayload.model_validate(payload)
    except (JWTError, ValidationError) as exc:
        raise ValueError("invalid refresh token") from exc
    if parsed.token_type != REFRESH_TOKEN_TYPE:
        raise ValueError("token is not a refresh token")
    return parsed
