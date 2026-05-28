"""add hire_date to employees

Revision ID: 20260528_0008
Revises: 20260528_0007
Create Date: 2026-05-28
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260528_0008"
down_revision: str | None = "20260528_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("employees", sa.Column("hire_date", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("employees", "hire_date")
