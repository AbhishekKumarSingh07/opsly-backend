"""add_technician_role

Adds 'technician' to the user_role_enum PostgreSQL type so that technician
users can be created and bulk-imported from CSV.

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-03-26 00:01:00.000000

"""
from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "c2d3e4f5a6b7"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE is not transactional in PostgreSQL but is safe
    # to run; IF NOT EXISTS prevents errors on re-runs.
    op.execute("ALTER TYPE user_role_enum ADD VALUE IF NOT EXISTS 'technician'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values natively.
    # Downgrade is a no-op; removing the value would require recreating the type.
    pass
