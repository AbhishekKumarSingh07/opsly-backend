"""fix_bulk_import_logs_add_updated_at

Adds the missing updated_at column to bulk_import_logs and fixes the id
column to have a server-side gen_random_uuid() default (the original
migration omitted both).

Revision ID: b1c2d3e4f5a6
Revises: a3f9c2d81b55
Create Date: 2026-03-26 00:00:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b1c2d3e4f5a6"
down_revision = "a3f9c2d81b55"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add the missing updated_at column (nullable first so existing rows are fine)
    op.add_column(
        "bulk_import_logs",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
    )
    # Back-fill so no NULLs remain
    op.execute(
        "UPDATE bulk_import_logs SET updated_at = created_at WHERE updated_at IS NULL"
    )

    # 2. Fix the id column — give it a gen_random_uuid() server default so
    #    SQLAlchemy can omit it from INSERT and let PostgreSQL fill it in.
    op.execute(
        "ALTER TABLE bulk_import_logs ALTER COLUMN id SET DEFAULT gen_random_uuid()"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE bulk_import_logs ALTER COLUMN id DROP DEFAULT"
    )
    op.drop_column("bulk_import_logs", "updated_at")
