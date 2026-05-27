"""add schedule confirmations

Revision ID: 20260527_0004
Revises: 20260527_0003
Create Date: 2026-05-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260527_0004"
down_revision: str | None = "20260527_0003a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "work_schedules",
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "schedule_confirmation_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requested_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("response_note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.ForeignKeyConstraint(["requested_by_id"], ["employees.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_schedule_confirmation_requests_employee_id"),
        "schedule_confirmation_requests",
        ["employee_id"],
        unique=False,
    )
    op.create_index(
        "ix_schedule_confirmation_requests_employee_status",
        "schedule_confirmation_requests",
        ["employee_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_schedule_confirmation_requests_employee_status",
        table_name="schedule_confirmation_requests",
    )
    op.drop_index(
        op.f("ix_schedule_confirmation_requests_employee_id"),
        table_name="schedule_confirmation_requests",
    )
    op.drop_table("schedule_confirmation_requests")
    op.drop_column("work_schedules", "confirmed_at")
