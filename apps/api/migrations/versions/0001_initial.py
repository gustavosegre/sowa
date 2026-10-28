"""initial schema: projects, sources, export_jobs

Revision ID: 0001
Revises:
Create Date: 2026-10-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("pipeline", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "sources",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("project_id", sa.String(32), sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("format", sa.String(16), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("detected", sa.JSON(), nullable=False),
        sa.Column("options", sa.JSON(), nullable=True),
        sa.Column("schema", sa.JSON(), nullable=True),
        sa.Column("parquet_path", sa.String(1000), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sources_project_id", "sources", ["project_id"])
    op.create_table(
        "export_jobs",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("project_id", sa.String(32), sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("node_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("progress", sa.Float(), nullable=False),
        sa.Column("format", sa.String(16), nullable=False),
        sa.Column("filename", sa.String(300), nullable=False),
        sa.Column("file_path", sa.String(1000), nullable=True),
        sa.Column("rows", sa.Integer(), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("error", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_export_jobs_project_id", "export_jobs", ["project_id"])


def downgrade() -> None:
    op.drop_table("export_jobs")
    op.drop_table("sources")
    op.drop_table("projects")
