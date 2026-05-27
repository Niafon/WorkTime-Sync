"""add avatar_url to teams

Revision ID: 20260527_0003a
Revises: 503561ee6849
Create Date: 2026-05-27

Note: исходный id был 20260527_0003, но при merge с ai-веткой он коллидировал
с ai_rag_tables. Переименовано в 0003a; цепочка теперь
  ai_rag_tables (0003) → password_hash → 0003a → schedule_confirmations (0004).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260527_0003a"
down_revision: str | None = "503561ee6849"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("teams", sa.Column("avatar_url", sa.String(length=512), nullable=True))


def downgrade() -> None:
    op.drop_column("teams", "avatar_url")
