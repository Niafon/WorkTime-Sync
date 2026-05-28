"""create employee_metric_snapshots

Revision ID: 20260528_0005
Revises: 20260528_0004
Create Date: 2026-05-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260528_0005"
down_revision: str | None = "20260528_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "employee_metric_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "employee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employees.id"),
            nullable=False,
        ),
        sa.Column("taken_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("days_since_update", sa.Integer(), nullable=False),
        sa.Column("actuality_score", sa.Float(), nullable=False),
        sa.Column("outside_events_count", sa.Integer(), nullable=False),
        sa.Column("total_events_count", sa.Integer(), nullable=False),
        sa.Column("conflict_rate", sa.Float(), nullable=False),
        sa.Column("load_level", sa.Float(), nullable=False),
        sa.Column("zone_factor", sa.Float(), nullable=False),
        sa.Column("hr_factor", sa.Float(), nullable=False),
        sa.Column("risk_score", sa.Float(), nullable=False),
        sa.Column("risk_level", sa.String(length=20), nullable=False),
    )
    op.create_index(
        "ix_employee_metric_snapshots_employee_id",
        "employee_metric_snapshots",
        ["employee_id"],
    )
    op.create_index(
        "ix_employee_metric_snapshots_taken_at",
        "employee_metric_snapshots",
        ["taken_at"],
    )
    op.create_index(
        "ix_employee_metric_snapshots_employee_taken",
        "employee_metric_snapshots",
        ["employee_id", "taken_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_employee_metric_snapshots_employee_taken",
        table_name="employee_metric_snapshots",
    )
    op.drop_index(
        "ix_employee_metric_snapshots_taken_at",
        table_name="employee_metric_snapshots",
    )
    op.drop_index(
        "ix_employee_metric_snapshots_employee_id",
        table_name="employee_metric_snapshots",
    )
    op.drop_table("employee_metric_snapshots")
