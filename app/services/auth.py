from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.vk_oauth import VKOAuthClient
from app.core.security import create_access_token
from app.models.employee import Employee
from app.repositories.employees import EmployeeRepository
from app.schemas.auth import AuthTokenResponse
from app.schemas.employee import EmployeeResponse

DEFAULT_VK_EMPLOYEE_ROLE = "employee"
DEFAULT_VK_EMPLOYEE_TIMEZONE = "Europe/Moscow"
DEFAULT_VK_EMPLOYEE_WORK_FORMAT = "remote"


class AuthService:
    def __init__(
        self,
        session: AsyncSession,
        vk_oauth_client: VKOAuthClient | None = None,
    ) -> None:
        self.session = session
        self.employees = EmployeeRepository(session)
        self.vk_oauth_client = vk_oauth_client or VKOAuthClient()

    def vk_authorization_url(self) -> str:
        return self.vk_oauth_client.authorization_url()

    async def authenticate_vk_code(self, code: str) -> AuthTokenResponse:
        vk_access_token = await self.vk_oauth_client.exchange_code_for_access_token(code)
        vk_user = await self.vk_oauth_client.get_user_info(vk_access_token)
        employee = await self.employees.get_by_vk_user_id(vk_user.vk_user_id)
        if employee is None:
            employee = await self.employees.create(
                Employee(
                    vk_user_id=vk_user.vk_user_id,
                    role=DEFAULT_VK_EMPLOYEE_ROLE,
                    full_name=vk_user.full_name,
                    timezone=DEFAULT_VK_EMPLOYEE_TIMEZONE,
                    work_format=DEFAULT_VK_EMPLOYEE_WORK_FORMAT,
                )
            )
            await self.session.commit()

        return AuthTokenResponse(
            access_token=create_access_token(employee_id=employee.id, role=employee.role),
            employee=EmployeeResponse.model_validate(employee),
        )
