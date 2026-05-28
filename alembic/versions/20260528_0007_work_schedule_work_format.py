"""add work_format to work_schedules

Revision ID: 20260528_0007
Revises: 20260528_0006
Create Date: 2026-05-28
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260528_0007"
down_revision: str | None = "20260528_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Backfill existing rows from the employee's current work_format, then
    # drop the server_default so future inserts must supply the column.
    op.add_column(
        "work_schedules",
        sa.Column("work_format", sa.String(length=30), nullable=False, server_default="office"),
    )
    op.execute(
        """
        UPDATE work_schedules ws
           SET work_format = e.work_format
          FROM employees e
         WHERE ws.employee_id = e.id
        """
    )
    op.alter_column("work_schedules", "work_format", server_default=None)


def downgrade() -> None:
    op.drop_column("work_schedules", "work_format")
