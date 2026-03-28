"""initial_schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-03-27

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # audit_log
    op.create_table('audit_log',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('table_name', sa.String(100), nullable=False),
        sa.Column('record_id', sa.String(36), nullable=False),
        sa.Column('action', sa.Enum('CREATE','UPDATE','DELETE','DISPATCH','BULK_IMPORT','CONFIG_CHANGE', name='audit_action_enum'), nullable=False),
        sa.Column('old_value', postgresql.JSONB(), nullable=True),
        sa.Column('new_value', postgresql.JSONB(), nullable=True),
        sa.Column('actor_id', sa.UUID(), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_audit_log_actor_id', 'audit_log', ['actor_id'])
    op.create_index('ix_audit_log_record_id', 'audit_log', ['record_id'])
    op.create_index('ix_audit_log_table_name', 'audit_log', ['table_name'])
    op.create_index('ix_audit_log_timestamp', 'audit_log', ['timestamp'])

    # users
    op.create_table('users',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('phone', sa.String(20), nullable=True),
        sa.Column('role', sa.Enum('owner','moderator','staff','technician', name='user_role_enum'), nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('last_login', sa.DateTime(timezone=True), nullable=True),
        sa.Column('must_change_password', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('phone'),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    # clients
    op.create_table('clients',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('contact_person', sa.String(255), nullable=True),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('phone', sa.String(20), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('portal_password_hash', sa.String(255), nullable=True),
        sa.Column('portal_enabled', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_by', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['deleted_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
    )

    # sites
    op.create_table('sites',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('city', sa.String(100), nullable=True),
        sa.Column('state', sa.String(100), nullable=True),
        sa.Column('contact_name', sa.String(255), nullable=True),
        sa.Column('contact_phone', sa.String(20), nullable=True),
        sa.Column('client_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_by', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['deleted_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )

    # dg_sets
    op.create_table('dg_sets',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('asset_tag', sa.String(100), nullable=False),
        sa.Column('make', sa.String(100), nullable=True),
        sa.Column('model', sa.String(100), nullable=True),
        sa.Column('kva_rating', sa.Float(), nullable=True),
        sa.Column('site_id', sa.UUID(), nullable=True),
        sa.Column('amc_expiry', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_by', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['deleted_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['site_id'], ['sites.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('asset_tag'),
    )

    # tenders
    op.create_table('tenders',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('reference_no', sa.String(50), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('client_name', sa.String(255), nullable=False),
        sa.Column('client_contact', sa.String(255), nullable=True),
        sa.Column('status', sa.Enum('BIDDING','WON','LOST','PROCUREMENT','INSTALLATION','COMMISSIONING','INVOICED','CLOSED', name='tender_status_enum'), nullable=False),
        sa.Column('bid_amount', sa.DECIMAL(14,2), nullable=True),
        sa.Column('awarded_amount', sa.DECIMAL(14,2), nullable=True),
        sa.Column('bid_submission_date', sa.Date(), nullable=True),
        sa.Column('award_date', sa.Date(), nullable=True),
        sa.Column('expected_completion', sa.Date(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_by', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.ForeignKeyConstraint(['deleted_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_tenders_reference_no', 'tenders', ['reference_no'], unique=True)

    # tender_documents
    op.create_table('tender_documents',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('tender_id', sa.UUID(), nullable=False),
        sa.Column('document_type', sa.String(50), nullable=False),
        sa.Column('s3_url', sa.String(1024), nullable=False),
        sa.Column('uploaded_by', sa.UUID(), nullable=False),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['tender_id'], ['tenders.id']),
        sa.ForeignKeyConstraint(['uploaded_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_tender_documents_tender_id', 'tender_documents', ['tender_id'])

    # tender_milestones
    op.create_table('tender_milestones',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('tender_id', sa.UUID(), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('due_date', sa.Date(), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['tender_id'], ['tenders.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_tender_milestones_tender_id', 'tender_milestones', ['tender_id'])

    # tickets
    op.create_table('tickets',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('reference_no', sa.String(50), nullable=False),
        sa.Column('site_id', sa.UUID(), nullable=True),
        sa.Column('dg_set_id', sa.UUID(), nullable=True),
        sa.Column('reported_issue', sa.Text(), nullable=False),
        sa.Column('status', sa.Enum('OPEN','IN_PROGRESS','PENDING_PARTS','RESOLVED','CLOSED','CANCELLED', name='ticket_status_enum'), nullable=False),
        sa.Column('priority', sa.Enum('LOW','MEDIUM','HIGH','CRITICAL', name='ticket_priority_enum'), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_by', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.ForeignKeyConstraint(['deleted_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['dg_set_id'], ['dg_sets.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['site_id'], ['sites.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_tickets_reference_no', 'tickets', ['reference_no'], unique=True)

    # ticket_technicians
    op.create_table('ticket_technicians',
        sa.Column('ticket_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(['ticket_id'], ['tickets.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('ticket_id', 'user_id'),
    )

    # ticket_photos
    op.create_table('ticket_photos',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('ticket_id', sa.UUID(), nullable=False),
        sa.Column('photo_type', sa.Enum('BEFORE','AFTER','PART_NEW','PART_OLD','SITE', name='photo_type_enum'), nullable=False),
        sa.Column('s3_url', sa.String(1024), nullable=False),
        sa.Column('gps_lat', sa.Float(), nullable=True),
        sa.Column('gps_lng', sa.Float(), nullable=True),
        sa.Column('uploaded_by', sa.UUID(), nullable=False),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['ticket_id'], ['tickets.id']),
        sa.ForeignKeyConstraint(['uploaded_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ticket_photos_ticket_id', 'ticket_photos', ['ticket_id'])

    # ticket_status_history
    op.create_table('ticket_status_history',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('ticket_id', sa.UUID(), nullable=False),
        sa.Column('from_status', sa.String(50), nullable=True),
        sa.Column('to_status', sa.String(50), nullable=False),
        sa.Column('changed_by', sa.UUID(), nullable=False),
        sa.Column('changed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['changed_by'], ['users.id']),
        sa.ForeignKeyConstraint(['ticket_id'], ['tickets.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ticket_status_history_ticket_id', 'ticket_status_history', ['ticket_id'])

    # attendance
    op.create_table('attendance',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('punch_in_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('punch_out_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('punch_in_gps_lat', sa.Float(), nullable=True),
        sa.Column('punch_in_gps_lng', sa.Float(), nullable=True),
        sa.Column('punch_out_gps_lat', sa.Float(), nullable=True),
        sa.Column('punch_out_gps_lng', sa.Float(), nullable=True),
        sa.Column('selfie_url', sa.String(1024), nullable=True),
        sa.Column('liveness_score', sa.Float(), nullable=True),
        sa.Column('flag_reason', sa.String(255), nullable=True),
        sa.Column('ticket_id', sa.UUID(), nullable=True),
        sa.Column('status', sa.Enum('PENDING_APPROVAL','APPROVED','FLAGGED','REJECTED', name='attendance_status_enum'), nullable=False),
        sa.Column('approved_by', sa.UUID(), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('approval_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['ticket_id'], ['tickets.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'date', name='uq_attendance_user_date'),
    )
    op.create_index('ix_attendance_user_id', 'attendance', ['user_id'])

    # expenses
    op.create_table('expenses',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('submitted_by', sa.UUID(), nullable=False),
        sa.Column('ticket_id', sa.UUID(), nullable=True),
        sa.Column('tender_id', sa.UUID(), nullable=True),
        sa.Column('category', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('amount', sa.DECIMAL(12,2), nullable=False),
        sa.Column('receipt_url', sa.String(1024), nullable=True),
        sa.Column('status', sa.Enum('DRAFT','SUBMITTED','APPROVED','REJECTED','REIMBURSED', name='expense_status_enum'), nullable=False),
        sa.Column('reviewed_by', sa.UUID(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('review_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_by', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['deleted_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['submitted_by'], ['users.id']),
        sa.ForeignKeyConstraint(['tender_id'], ['tenders.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['ticket_id'], ['tickets.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_expenses_submitted_by', 'expenses', ['submitted_by'])

    # bulk_import_logs
    op.create_table('bulk_import_logs',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('import_type', sa.String(50), nullable=False),
        sa.Column('filename', sa.String(255), nullable=True),
        sa.Column('total_rows', sa.Integer(), nullable=False),
        sa.Column('success_rows', sa.Integer(), nullable=False),
        sa.Column('failed_rows', sa.Integer(), nullable=False),
        sa.Column('errors', postgresql.JSONB(), nullable=True),
        sa.Column('imported_by', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['imported_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # salary_records
    op.create_table('salary_records',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('month', sa.Integer(), nullable=False),
        sa.Column('gross_salary', sa.DECIMAL(12,2), nullable=False),
        sa.Column('advance_deducted', sa.DECIMAL(12,2), nullable=False),
        sa.Column('net_payable', sa.DECIMAL(12,2), nullable=False),
        sa.Column('status', sa.Enum('PENDING','PAID', name='salary_status_enum'), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('recorded_by', sa.UUID(), nullable=False),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['recorded_by'], ['users.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'year', 'month', name='uq_salary_user_year_month'),
    )

    # advance_payments
    op.create_table('advance_payments',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('amount', sa.DECIMAL(12,2), nullable=False),
        sa.Column('payment_date', sa.Date(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('given_by', sa.UUID(), nullable=False),
        sa.Column('salary_record_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['given_by'], ['users.id']),
        sa.ForeignKeyConstraint(['salary_record_id'], ['salary_records.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── NEW INVENTORY TABLES ─────────────────────────────────────────────────

    # inventory_categories
    op.create_table('inventory_categories',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('category_name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_by', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['deleted_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('category_name'),
    )
    op.create_index('ix_inventory_categories_category_name', 'inventory_categories', ['category_name'])

    # inventory_items (new schema)
    op.create_table('inventory_items',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('part_name', sa.String(255), nullable=False),
        sa.Column('part_number', sa.String(100), nullable=False),
        sa.Column('category_id', sa.UUID(), nullable=True),
        sa.Column('barcode', sa.String(100), nullable=True),
        sa.Column('unit_cost', sa.DECIMAL(12,2), nullable=False, server_default='0'),
        sa.Column('quantity', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('low_stock_threshold', sa.Integer(), nullable=False, server_default='10'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_by', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['category_id'], ['inventory_categories.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['deleted_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('part_number'),
        sa.UniqueConstraint('barcode'),
    )
    op.create_index('ix_inventory_items_part_number', 'inventory_items', ['part_number'])
    op.create_index('ix_inventory_items_barcode', 'inventory_items', ['barcode'])
    op.create_index('ix_inventory_items_category_id', 'inventory_items', ['category_id'])

    # dispatch_history
    op.create_table('dispatch_history',
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

    # low_stock_configs
    op.create_table('low_stock_configs',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('inventory_item_id', sa.UUID(), nullable=True),
        sa.Column('threshold', sa.Integer(), nullable=False),
        sa.Column('configured_by', sa.UUID(), nullable=False),
        sa.Column('configured_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['configured_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['inventory_item_id'], ['inventory_items.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('inventory_item_id'),
    )
    op.create_index('ix_low_stock_configs_inventory_item_id', 'low_stock_configs', ['inventory_item_id'])


def downgrade() -> None:
    op.drop_table('low_stock_configs')
    op.drop_table('dispatch_history')
    op.drop_table('inventory_items')
    op.drop_table('inventory_categories')
    op.drop_table('advance_payments')
    op.drop_table('salary_records')
    op.drop_table('bulk_import_logs')
    op.drop_table('expenses')
    op.drop_table('attendance')
    op.drop_table('ticket_status_history')
    op.drop_table('ticket_photos')
    op.drop_table('ticket_technicians')
    op.drop_table('tickets')
    op.drop_table('dg_sets')
    op.drop_table('tender_milestones')
    op.drop_table('tender_documents')
    op.drop_table('tenders')
    op.drop_table('sites')
    op.drop_table('clients')
    op.drop_table('users')
    op.drop_table('audit_log')
    op.execute("DROP TYPE IF EXISTS audit_action_enum")
    op.execute("DROP TYPE IF EXISTS user_role_enum")
    op.execute("DROP TYPE IF EXISTS tender_status_enum")
    op.execute("DROP TYPE IF EXISTS ticket_status_enum")
    op.execute("DROP TYPE IF EXISTS ticket_priority_enum")
    op.execute("DROP TYPE IF EXISTS photo_type_enum")
    op.execute("DROP TYPE IF EXISTS attendance_status_enum")
    op.execute("DROP TYPE IF EXISTS expense_status_enum")
    op.execute("DROP TYPE IF EXISTS salary_status_enum")
