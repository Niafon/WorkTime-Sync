"""employee_metrics.employee_id UNIQUE for ON CONFLICT upsert

Revision ID: 20260528_0010
Revises: 20260528_0009
Create Date: 2026-05-28
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260528_0010"
down_revision: str | None = "20260528_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Старый индекс был неуникальным — заменяем на uniq, чтобы конкурирующие
    # `INSERT ... ON CONFLICT (employee_id) DO UPDATE` в repositories/employee_metrics.py
    # выполнялись атомарно на уровне БД и больше не плодили дубликаты при
    # параллельном recompute_for_employee_id.
    op.drop_index("ix_employee_metrics_employee_id", table_name="employee_metrics")
    op.create_index(
        "ix_employee_metrics_employee_id",
        "employee_metrics",
        ["employee_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_employee_metrics_employee_id", table_name="employee_metrics")
    op.create_index(
        "ix_employee_metrics_employee_id",
        "employee_metrics",
        ["employee_id"],
        unique=False,
    )
