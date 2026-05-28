"""add employees.employment_type column with check constraint

Revision ID: 20260528_0006
Revises: 3e7fde1f7d43
Create Date: 2026-05-28

Note: chained after 3e7fde1f7d43 (the actual DB head) rather than 20260528_0005
because the repo has two competing migrations sharing id 20260528_0005
(employee_hire_date and employee_metric_snapshots). Only metric_snapshots was
actually applied to the DB; hire_date is an orphan branch.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260528_0006"
down_revision: str | None = "3e7fde1f7d43"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_VALID_TYPES = ("full_time", "part_time", "contract")
_VALID_TYPES_SQL = ", ".join(f"'{value}'" for value in _VALID_TYPES)


def upgrade() -> None:
    # server_default backfills existing rows и оставляется навсегда, чтобы
    # сторонние пути вставки (seed, ручные fixture) не падали при отсутствии поля;
    # API-схемы (EmployeeCreate, EmployeeFullCreate) требуют значение явно.
    op.add_column(
        "employees",
        sa.Column(
            "employment_type",
            sa.String(length=20),
            nullable=False,
            server_default="full_time",
        ),
    )
    op.create_check_constraint(
        "ck_employees_employment_type_valid",
        "employees",
        f"employment_type in ({_VALID_TYPES_SQL})",
    )


def downgrade() -> None:
    op.drop_constraint("ck_employees_employment_type_valid", "employees", type_="check")
    op.drop_column("employees", "employment_type")
