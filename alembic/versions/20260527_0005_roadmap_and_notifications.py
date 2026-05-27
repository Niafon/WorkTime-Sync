"""add roadmap items and notifications

Revision ID: 20260527_0005
Revises: 20260527_0004
Create Date: 2026-05-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260527_0005"
down_revision: str | None = "20260527_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_OPEN_STATUSES_SQL = (
    "status IN ('pending','requested','acknowledged','updated','deferred')"
)


def upgrade() -> None:
    op.create_table(
        "roadmap_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject_type", sa.String(length=20), nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("team_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("recommendation_code", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("priority_score", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
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
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assigned_to_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "confirmation_request_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("metric_snapshot", postgresql.JSONB(), nullable=True),
        sa.ForeignKeyConstraint(
            ["employee_id"], ["employees.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["assigned_to_id"], ["employees.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["employees.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["confirmation_request_id"],
            ["schedule_confirmation_requests.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_roadmap_items_subject",
        "roadmap_items",
        ["subject_type", "subject_id"],
        unique=False,
    )
    op.create_index(
        "ix_roadmap_items_status", "roadmap_items", ["status"], unique=False
    )
    op.create_index(
        "ix_roadmap_items_priority",
        "roadmap_items",
        ["priority_score"],
        unique=False,
    )
    op.create_index(
        "ix_roadmap_items_employee_id",
        "roadmap_items",
        ["employee_id"],
        unique=False,
    )
    op.create_index(
        "ix_roadmap_items_team_id", "roadmap_items", ["team_id"], unique=False
    )
    op.create_index(
        "ix_roadmap_items_assigned_to_id",
        "roadmap_items",
        ["assigned_to_id"],
        unique=False,
    )
    op.create_index(
        "uq_roadmap_open_per_subject_code",
        "roadmap_items",
        ["subject_type", "subject_id", "recommendation_code"],
        unique=True,
        postgresql_where=sa.text(_OPEN_STATUSES_SQL),
    )

    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recipient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.Column(
            "related_roadmap_item_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["recipient_id"], ["employees.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["related_roadmap_item_id"],
            ["roadmap_items.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_notifications_recipient_id",
        "notifications",
        ["recipient_id"],
        unique=False,
    )
    op.create_index(
        "ix_notifications_unread",
        "notifications",
        ["recipient_id"],
        unique=False,
        postgresql_where=sa.text("read_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_unread", table_name="notifications")
    op.drop_index("ix_notifications_recipient_id", table_name="notifications")
    op.drop_table("notifications")

    op.drop_index(
        "uq_roadmap_open_per_subject_code", table_name="roadmap_items"
    )
    op.drop_index("ix_roadmap_items_assigned_to_id", table_name="roadmap_items")
    op.drop_index("ix_roadmap_items_team_id", table_name="roadmap_items")
    op.drop_index("ix_roadmap_items_employee_id", table_name="roadmap_items")
    op.drop_index("ix_roadmap_items_priority", table_name="roadmap_items")
    op.drop_index("ix_roadmap_items_status", table_name="roadmap_items")
    op.drop_index("ix_roadmap_items_subject", table_name="roadmap_items")
    op.drop_table("roadmap_items")
