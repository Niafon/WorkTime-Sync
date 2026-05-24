"""initial schema

Revision ID: 20260524_0001
Revises:
Create Date: 2026-05-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260524_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "employees",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("vk_user_id", sa.String(length=64), nullable=True),
        sa.Column("role", sa.String(length=40), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("position", sa.String(length=150), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("work_format", sa.String(length=30), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("vk_user_id"),
    )
    op.create_table(
        "teams",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "activity_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("source", sa.String(length=60), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("start_dt", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_dt", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("is_recurring", sa.Boolean(), nullable=False),
        sa.Column("is_outside_schedule", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_activity_events_employee_id"),
        "activity_events",
        ["employee_id"],
        unique=False,
    )
    op.create_table(
        "employee_metrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("days_since_update", sa.Integer(), nullable=False),
        sa.Column("actuality_score", sa.Float(), nullable=False),
        sa.Column("outside_events_count", sa.Integer(), nullable=False),
        sa.Column("total_events_count", sa.Integer(), nullable=False),
        sa.Column("conflict_rate", sa.Float(), nullable=False),
        sa.Column("load_level", sa.Float(), nullable=False),
        sa.Column("risk_score", sa.Float(), nullable=False),
        sa.Column("risk_level", sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_employee_metrics_employee_id"),
        "employee_metrics",
        ["employee_id"],
        unique=True,
    )
    op.create_table(
        "schedule_exceptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.String(length=40), nullable=False),
        sa.Column("start_dt", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_dt", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_schedule_exceptions_employee_id"),
        "schedule_exceptions",
        ["employee_id"],
        unique=False,
    )
    op.create_table(
        "team_members",
        sa.Column("team_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role_in_team", sa.String(length=80), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"]),
        sa.PrimaryKeyConstraint("team_id", "employee_id"),
    )
    op.create_index("ix_team_members_employee_id", "team_members", ["employee_id"], unique=False)
    op.create_index("ix_team_members_team_id", "team_members", ["team_id"], unique=False)
    op.create_table(
        "work_schedules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("work_days", postgresql.ARRAY(sa.Integer()), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("last_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_work_schedules_employee_id"),
        "work_schedules",
        ["employee_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_work_schedules_employee_id"), table_name="work_schedules")
    op.drop_table("work_schedules")
    op.drop_index("ix_team_members_team_id", table_name="team_members")
    op.drop_index("ix_team_members_employee_id", table_name="team_members")
    op.drop_table("team_members")
    op.drop_index(op.f("ix_schedule_exceptions_employee_id"), table_name="schedule_exceptions")
    op.drop_table("schedule_exceptions")
    op.drop_index(op.f("ix_employee_metrics_employee_id"), table_name="employee_metrics")
    op.drop_table("employee_metrics")
    op.drop_index(op.f("ix_activity_events_employee_id"), table_name="activity_events")
    op.drop_table("activity_events")
    op.drop_table("teams")
    op.drop_table("employees")
