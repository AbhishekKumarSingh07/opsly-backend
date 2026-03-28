"""drop dispatch_history table

Dispatch feature was removed entirely from the codebase.
This migration drops the orphaned dispatch_history table that was
created by 0001_initial_schema but is no longer referenced anywhere.

Revision ID: 0005_drop_dispatch
Revises: 0004_fix_bulk_import
Create Date: 2025-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0005_drop_dispatch'
down_revision = '0004_fix_bulk_import'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop index first, then the table
    op.drop_index('ix_dispatch_history_inventory_item_id', table_name='dispatch_history')
    op.drop_table('dispatch_history')


def downgrade() -> None:
    # Recreate the table if rolling back (matches 0001_initial_schema definition)
    op.create_table(
        'dispatch_history',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('inventory_item_id', sa.UUID(), nullable=False),
        sa.Column('part_number', sa.String(100), nullable=False),
        sa.Column('barcode', sa.String(100), nullable=True),
        sa.Column('quantity_dispatched', sa.Integer(), nullable=False),
        sa.Column('dispatched_by', sa.UUID(), nullable=False),
        sa.Column('dispatched_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['dispatched_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['inventory_item_id'], ['inventory_items.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_dispatch_history_inventory_item_id', 'dispatch_history', ['inventory_item_id'])
