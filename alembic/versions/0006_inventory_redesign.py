"""inventory redesign — optional part_number, drop LowStockConfig, add InventoryDispatch

Revision ID: 0006_inventory_redesign
Revises: 0005_drop_dispatch
Create Date: 2025-06-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0006_inventory_redesign'
down_revision = '0005_drop_dispatch'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Make part_number nullable on inventory_items
    op.alter_column('inventory_items', 'part_number',
                    existing_type=sa.String(100),
                    nullable=True)

    # 2. Drop low_stock_configs table (if it exists)
    op.execute("DROP TABLE IF EXISTS low_stock_configs CASCADE")

    # 3. Drop legacy tables that were never used (if they exist)
    op.execute("DROP TABLE IF EXISTS inventory_stock CASCADE")
    op.execute("DROP TABLE IF EXISTS inventory_movements CASCADE")

    # 4. Create inventory_dispatches table
    op.create_table(
        'inventory_dispatches',
        sa.Column('id', postgresql.UUID(as_uuid=True),
                  server_default=sa.text('gen_random_uuid()'),
                  nullable=False),
        sa.Column('inventory_item_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('ticket_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('dispatched_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('dispatched_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('part_number_dispatched', sa.String(100), nullable=True),
        sa.Column('barcode_dispatched', sa.String(100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('returned_quantity', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('returned_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('returned_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['inventory_item_id'], ['inventory_items.id'],
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['ticket_id'], ['tickets.id'],
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['dispatched_by'], ['users.id'],
                                ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['returned_by'], ['users.id'],
                                ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_inventory_dispatches_item_id',
                    'inventory_dispatches', ['inventory_item_id'])
    op.create_index('ix_inventory_dispatches_ticket_id',
                    'inventory_dispatches', ['ticket_id'])


def downgrade() -> None:
    # 1. Drop new table
    op.drop_index('ix_inventory_dispatches_ticket_id',
                  table_name='inventory_dispatches')
    op.drop_index('ix_inventory_dispatches_item_id',
                  table_name='inventory_dispatches')
    op.drop_table('inventory_dispatches')

    # 2. Restore part_number NOT NULL
    op.alter_column('inventory_items', 'part_number',
                    existing_type=sa.String(100),
                    nullable=False)

    # Note: low_stock_configs is NOT recreated on downgrade by design.
