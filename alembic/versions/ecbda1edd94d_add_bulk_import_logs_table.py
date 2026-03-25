"""add_bulk_import_logs_table

Revision ID: ecbda1edd94d
Revises: f17fecd70da7
Create Date: 2026-03-16 16:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "ecbda1edd94d"
down_revision = "f17fecd70da7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bulk_import_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "import_type",
            sa.Enum("staff", "inventory", name="importtype"),
            nullable=False,
        ),
        sa.Column(
            "file_format",
            sa.Enum("csv", "xlsx", "json", name="importformat"),
            nullable=False,
        ),
        sa.Column("original_filename", sa.String(), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False),
        sa.Column("success_count", sa.Integer(), nullable=False),
        sa.Column("failure_count", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "completed", "partial", "failed", name="importstatus"),
            nullable=False,
        ),
        sa.Column("error_details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("imported_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["imported_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_bulk_import_logs_imported_by"),
        "bulk_import_logs",
        ["imported_by"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_bulk_import_logs_imported_by"), table_name="bulk_import_logs"
    )
    op.drop_table("bulk_import_logs")
    op.execute("DROP TYPE IF EXISTS importtype")
    op.execute("DROP TYPE IF EXISTS importformat")
    op.execute("DROP TYPE IF EXISTS importstatus")
