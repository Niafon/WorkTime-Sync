from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.vk_oauth import VKOAuthClient, VKOAuthStateError, verify_vk_oauth_state
from app.core.passwords import hash_password, verify_password
from app.core.roles import EmployeeRole
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
)
from app.models.employee import Employee
from app.repositories.employees import EmployeeRepository
from app.repositories.refresh_tokens import RefreshTokenRepository
from app.schemas.auth import AuthResponse, UserResponse

DEFAULT_VK_EMPLOYEE_ROLE = EmployeeRole.EMPLOYEE
DEFAULT_EMPLOYEE_TIMEZONE = "Europe/Moscow"
DEFAULT_EMPLOYEE_WORK_FORMAT = "remote"
DEFAULT_REGISTER_ROLE = EmployeeRole.EMPLOYEE


@dataclass(frozen=True, slots=True)
class IssuedTokens:
    """Бандл с обоими токенами и временем жизни refresh — для установки cookie."""

    response: AuthResponse
    refresh_token: str
    refresh_expires_at: datetime


class RefreshReuseDetectedError(ValueError):
    """Поднимается при попытке использовать уже отозванный refresh.

    Эндпоинт обязан вернуть 401 + очистить cookie; все активные refresh-токены
    сотрудника к этому моменту уже отозваны в БД.
    """


class AuthService:
    def __init__(
        self,
        session: AsyncSession,
        vk_oauth_client: VKOAuthClient | None = None,
    ) -> None:
        self.session = session
        self.employees = EmployeeRepository(session)
        self.refresh_tokens = RefreshTokenRepository(session)
        self.vk_oauth_client = vk_oauth_client or VKOAuthClient()

    def vk_authorization_url(self) -> str:
        url, _state = self.vk_oauth_client.authorization_url()
        return url

    async def authenticate_vk_code(self, code: str, state: str) -> IssuedTokens:
        try:
            verify_vk_oauth_state(state)
        except VKOAuthStateError as exc:
            raise ValueError(f"invalid OAuth state: {exc}") from exc
        vk_access_token = await self.vk_oauth_client.exchange_code_for_access_token(code)
        vk_user = await self.vk_oauth_client.get_user_info(vk_access_token)
        employee = await self.employees.get_by_vk_user_id(vk_user.vk_user_id)
        if employee is None:
            employee = await self.employees.create(
                Employee(
                    vk_user_id=vk_user.vk_user_id,
                    role=DEFAULT_VK_EMPLOYEE_ROLE,
                    full_name=vk_user.full_name,
                    timezone=DEFAULT_EMPLOYEE_TIMEZONE,
                    work_format=DEFAULT_EMPLOYEE_WORK_FORMAT,
                )
            )
        tokens = await self._issue_token_pair(employee)
        await self.session.commit()
        return tokens

    async def register(self, *, email: str, password: str, full_name: str) -> IssuedTokens:
        existing = await self.employees.get_by_email(email)
        if existing is not None:
            raise ValueError("email already registered")

        employee = await self.employees.create(
            Employee(
                email=email,
                password_hash=hash_password(password),
                full_name=full_name,
                role=DEFAULT_REGISTER_ROLE,
                timezone=DEFAULT_EMPLOYEE_TIMEZONE,
                work_format=DEFAULT_EMPLOYEE_WORK_FORMAT,
            )
        )
        tokens = await self._issue_token_pair(employee)
        await self.session.commit()
        return tokens

    async def login(self, *, email: str, password: str) -> IssuedTokens:
        employee = await self.employees.get_by_email(email)
        if employee is None or not employee.password_hash:
            raise ValueError("invalid email or password")
        if not verify_password(password, employee.password_hash):
            raise ValueError("invalid email or password")
        tokens = await self._issue_token_pair(employee)
        await self.session.commit()
        return tokens

    async def refresh(self, refresh_token: str) -> IssuedTokens:
        """Ротация refresh + reuse detection.

        Декодируем входящий refresh, ищем по `jti` в БД. Если уже отозван —
        это reuse: отзываем все refresh-токены сотрудника и бросаем
        `RefreshReuseDetectedError`. Иначе выдаём новую пару, старый помечаем
        revoked с `replaced_by_jti` = новый jti.
        """
        try:
            payload = decode_refresh_token(refresh_token)
        except ValueError as exc:
            raise ValueError("invalid refresh token") from exc

        stored = await self.refresh_tokens.get_by_jti(payload.jti)
        if stored is None:
            raise ValueError("invalid refresh token")

        if stored.revoked_at is not None:
            await self.refresh_tokens.revoke_all_for_employee(stored.employee_id)
            await self.session.commit()
            raise RefreshReuseDetectedError("refresh token reuse detected")

        if stored.expires_at <= datetime.now(UTC):
            raise ValueError("refresh token expired")

        employee = await self.employees.get(stored.employee_id)
        if employee is None:
            raise ValueError("employee no longer exists")

        tokens = await self._issue_token_pair(employee)
        new_payload = decode_refresh_token(tokens.refresh_token)
        await self.refresh_tokens.mark_revoked(stored, replaced_by_jti=new_payload.jti)
        await self.session.commit()
        return tokens

    async def logout(self, refresh_token: str | None) -> None:
        """Идемпотентно: отсутствие или невалидный токен → no-op."""
        if not refresh_token:
            return
        try:
            payload = decode_refresh_token(refresh_token)
        except ValueError:
            return
        stored = await self.refresh_tokens.get_by_jti(payload.jti)
        if stored is None or stored.revoked_at is not None:
            return
        await self.refresh_tokens.mark_revoked(stored)
        await self.session.commit()

    async def _issue_token_pair(self, employee: Employee) -> IssuedTokens:
        access = create_access_token(employee_id=employee.id, role=employee.role)
        jti = uuid4().hex
        refresh, expires_at = create_refresh_token(employee_id=employee.id, jti=jti)
        await self.refresh_tokens.create(
            employee_id=employee.id,
            jti=jti,
            issued_at=datetime.now(UTC),
            expires_at=expires_at,
        )
        return IssuedTokens(
            response=AuthResponse(token=access, user=UserResponse.from_employee(employee)),
            refresh_token=refresh,
            refresh_expires_at=expires_at,
        )
