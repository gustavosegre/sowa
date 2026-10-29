"""access token instead of users (Flowa pattern); project workspaces

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_sessions_user_id", table_name="sessions")
    op.drop_table("sessions")
    op.drop_table("users")
    with op.batch_alter_table("projects") as b:
        b.drop_column("owner_id")
        b.add_column(sa.Column("workspace", sa.String(100), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("projects") as b:
        b.drop_column("workspace")
        b.add_column(sa.Column("owner_id", sa.String(32), nullable=True))
    op.create_table(
        "users",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("username", sa.String(64), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
