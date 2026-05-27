"""add zone_factor and hr_factor to employee_metrics

Revision ID: 20260528_0003
Revises: 20260528_0002
Create Date: 2026-05-28
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260528_0003"
down_revision: str | None = "20260528_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "employee_metrics",
        sa.Column("zone_factor", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "employee_metrics",
        sa.Column("hr_factor", sa.Float(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("employee_metrics", "hr_factor")
    op.drop_column("employee_metrics", "zone_factor")
