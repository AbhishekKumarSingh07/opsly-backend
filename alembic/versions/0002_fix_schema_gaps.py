"""fix_schema_gaps

Adds missing columns to tickets and dg_sets, and fixes ticket_status_enum.

Revision ID: 0002_fix_schema_gaps
Revises: 0001_initial_schema
Create Date: 2026-03-27

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0002_fix_schema_gaps'
down_revision: Union[str, None] = '0001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── tickets: add missing columns ─────────────────────────────────────────
    op.add_column('tickets', sa.Column('notes', sa.Text(), nullable=True))
    op.add_column('tickets', sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('tickets', sa.Column('invoiced_at', sa.DateTime(timezone=True), nullable=True))

    # ── ticket_status_enum: add missing values ───────────────────────────────
    # PostgreSQL requires ALTER TYPE ... ADD VALUE for enum additions
    op.execute("ALTER TYPE ticket_status_enum ADD VALUE IF NOT EXISTS 'ASSIGNED'")
    op.execute("ALTER TYPE ticket_status_enum ADD VALUE IF NOT EXISTS 'EN_ROUTE'")
    op.execute("ALTER TYPE ticket_status_enum ADD VALUE IF NOT EXISTS 'WAITING_FOR_PARTS'")
    op.execute("ALTER TYPE ticket_status_enum ADD VALUE IF NOT EXISTS 'COMPLETED'")
    op.execute("ALTER TYPE ticket_status_enum ADD VALUE IF NOT EXISTS 'INVOICED'")

    # ── dg_sets: add missing columns ─────────────────────────────────────────
    op.add_column('dg_sets', sa.Column('serial_no', sa.String(100), nullable=True))
    op.add_column('dg_sets', sa.Column('capacity_kva', sa.Float(), nullable=True))
    op.add_column('dg_sets', sa.Column('installation_date', sa.Date(), nullable=True))
    op.add_column('dg_sets', sa.Column('last_service_date', sa.Date(), nullable=True))
    op.add_column('dg_sets', sa.Column('next_service_date', sa.Date(), nullable=True))
    op.add_column('dg_sets', sa.Column('service_interval_days', sa.Integer(), nullable=False, server_default='90'))
    op.add_column('dg_sets', sa.Column('notes', sa.Text(), nullable=True))

    # dg_sets: rename kva_rating -> capacity_kva is handled by the new column above;
    # kva_rating may already exist from 0001 migration, we keep both for safety.
    # Add unique constraint on serial_no
    op.create_unique_constraint('uq_dg_sets_serial_no', 'dg_sets', ['serial_no'])

    # ── dg_sets: rename asset_tag column to asset_tag (already exists), add asset_tag index ──
    # The model uses asset_tag as unique — already covered by 0001 migration.


def downgrade() -> None:
    op.drop_constraint('uq_dg_sets_serial_no', 'dg_sets', type_='unique')
    op.drop_column('dg_sets', 'notes')
    op.drop_column('dg_sets', 'service_interval_days')
    op.drop_column('dg_sets', 'next_service_date')
    op.drop_column('dg_sets', 'last_service_date')
    op.drop_column('dg_sets', 'installation_date')
    op.drop_column('dg_sets', 'capacity_kva')
    op.drop_column('dg_sets', 'serial_no')
    op.drop_column('tickets', 'invoiced_at')
    op.drop_column('tickets', 'completed_at')
    op.drop_column('tickets', 'notes')
