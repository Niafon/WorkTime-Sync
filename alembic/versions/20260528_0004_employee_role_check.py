"""add check constraint on employees.role

Revision ID: 20260528_0004
Revises: 20260528_0003
Create Date: 2026-05-28

Note: prior id was 20260527_0005, but that id collided with
20260527_0005_roadmap_and_notifications. Moved to the tail of the chain
so the existing applied revisions are not disturbed.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260528_0004"
down_revision: str | None = "20260528_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_VALID_ROLES = ("admin", "manager", "hr", "pm", "analyst", "employee")
_VALID_ROLES_SQL = ", ".join(f"'{role}'" for role in _VALID_ROLES)


def upgrade() -> None:
    op.execute(
        f"update employees set role = 'employee' where role not in ({_VALID_ROLES_SQL})"
    )
    op.create_check_constraint(
        "ck_employees_role_valid",
        "employees",
        f"role in ({_VALID_ROLES_SQL})",
    )


def downgrade() -> None:
    op.drop_constraint("ck_employees_role_valid", "employees", type_="check")
