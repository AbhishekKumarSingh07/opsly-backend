"""fix_bulk_import_logs_schema

Fixes bulk_import_logs column names to match the model:
- filename        → original_filename
- success_rows    → success_count
- failed_rows     → failure_count
- errors          → error_details
Adds missing columns: file_format, status (with enum types).
Also adds missing salary_status_enum values: PARTIAL, ON_HOLD.

Revision ID: 0004_fix_bulk_import
Revises: 0003_fix_adv_pay
Create Date: 2026-03-27

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0004_fix_bulk_import'
down_revision: Union[str, None] = '0003_fix_adv_pay'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── bulk_import_logs: rename columns to match model ──────────────────────
    op.alter_column('bulk_import_logs', 'filename',      new_column_name='original_filename')
    op.alter_column('bulk_import_logs', 'success_rows',  new_column_name='success_count')
    op.alter_column('bulk_import_logs', 'failed_rows',   new_column_name='failure_count')
    op.alter_column('bulk_import_logs', 'errors',        new_column_name='error_details')

    # ── bulk_import_logs: add missing file_format column ─────────────────────
    # Create the enum type first, then add the column
    op.execute("CREATE TYPE import_format_enum AS ENUM ('xlsx', 'csv', 'json')")
    op.add_column(
        'bulk_import_logs',
        sa.Column(
            'file_format',
            sa.Enum('xlsx', 'csv', 'json', name='import_format_enum', create_type=False),
            nullable=False,
            server_default='csv',
        ),
    )

    # ── bulk_import_logs: add missing status column ───────────────────────────
    op.execute("CREATE TYPE import_status_enum AS ENUM ('pending', 'completed', 'partial', 'failed')")
    op.add_column(
        'bulk_import_logs',
        sa.Column(
            'status',
            sa.Enum('pending', 'completed', 'partial', 'failed', name='import_status_enum', create_type=False),
            nullable=False,
            server_default='completed',
        ),
    )

    # ── bulk_import_logs: fix import_type column (was String, keep as-is) ────
    # The import_type column is varchar(50) in DB but the model uses an Enum.
    # Create the enum type and cast the column.
    op.execute("CREATE TYPE import_type_enum AS ENUM ('inventory', 'staff', 'categories')")
    op.execute("""
        ALTER TABLE bulk_import_logs
        ALTER COLUMN import_type TYPE import_type_enum
        USING import_type::import_type_enum
    """)

    # ── salary_status_enum: add missing values ────────────────────────────────
    op.execute("ALTER TYPE salary_status_enum ADD VALUE IF NOT EXISTS 'PARTIAL'")
    op.execute("ALTER TYPE salary_status_enum ADD VALUE IF NOT EXISTS 'ON_HOLD'")


def downgrade() -> None:
    op.alter_column('bulk_import_logs', 'original_filename', new_column_name='filename')
    op.alter_column('bulk_import_logs', 'success_count',     new_column_name='success_rows')
    op.alter_column('bulk_import_logs', 'failure_count',     new_column_name='failed_rows')
    op.alter_column('bulk_import_logs', 'error_details',     new_column_name='errors')
    op.drop_column('bulk_import_logs', 'file_format')
    op.drop_column('bulk_import_logs', 'status')
