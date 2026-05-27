from enum import StrEnum


class EmployeeRole(StrEnum):
    ADMIN = "admin"
    MANAGER = "manager"
    HR = "hr"
    PM = "pm"
    ANALYST = "analyst"
    EMPLOYEE = "employee"


ROLE_LABEL_RU: dict[EmployeeRole, str] = {
    EmployeeRole.ADMIN: "Администратор",
    EmployeeRole.MANAGER: "Руководитель",
    EmployeeRole.HR: "HR-специалист",
    EmployeeRole.PM: "Проектный менеджер",
    EmployeeRole.ANALYST: "Аналитик",
    EmployeeRole.EMPLOYEE: "Сотрудник",
}

MANAGEMENT_ROLES: frozenset[EmployeeRole] = frozenset(
    {
        EmployeeRole.ADMIN,
        EmployeeRole.MANAGER,
        EmployeeRole.HR,
        EmployeeRole.PM,
    }
)
