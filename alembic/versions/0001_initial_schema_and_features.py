"""initial schema and feature additions

Revision ID: 0001
Revises:
Create Date: 2025-01-01 00:00:00.000000

Covers:
  - Full initial database schema (all core tables)
  - users.must_change_password (bool, NOT NULL DEFAULT false)
  - users.created_by (UUID, nullable FK → users.id)
  - bulk_import_logs table (import history)
  - import_type_enum, import_format_enum, import_status_enum PG enums
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Enums ────────────────────────────────────────────────────────────────
    user_role_enum = postgresql.ENUM(
        "owner", "moderator", "staff", "technician", "client",
        name="user_role_enum", create_type=False,
    )
    user_role_enum.create(op.get_bind(), checkfirst=True)

    attendance_status_enum = postgresql.ENUM(
        "pending", "approved", "rejected", "flagged",
        name="attendance_status_enum", create_type=False,
    )
    attendance_status_enum.create(op.get_bind(), checkfirst=True)

    expense_status_enum = postgresql.ENUM(
        "pending", "approved", "rejected", "reimbursed",
        name="expense_status_enum", create_type=False,
    )
    expense_status_enum.create(op.get_bind(), checkfirst=True)

    ticket_status_enum = postgresql.ENUM(
        "open", "assigned", "in_progress", "pending_parts", "resolved", "closed", "cancelled",
        name="ticket_status_enum", create_type=False,
    )
    ticket_status_enum.create(op.get_bind(), checkfirst=True)

    ticket_priority_enum = postgresql.ENUM(
        "low", "medium", "high", "critical",
        name="ticket_priority_enum", create_type=False,
    )
    ticket_priority_enum.create(op.get_bind(), checkfirst=True)

    photo_type_enum = postgresql.ENUM(
        "before", "after", "signature",
        name="photo_type_enum", create_type=False,
    )
    photo_type_enum.create(op.get_bind(), checkfirst=True)

    inventory_status_enum = postgresql.ENUM(
        "available", "in_field", "under_repair", "retired",
        name="inventory_status_enum", create_type=False,
    )
    inventory_status_enum.create(op.get_bind(), checkfirst=True)

    tender_status_enum = postgresql.ENUM(
        "draft", "submitted", "under_review", "won", "lost", "cancelled",
        name="tender_status_enum", create_type=False,
    )
    tender_status_enum.create(op.get_bind(), checkfirst=True)

    import_type_enum = postgresql.ENUM(
        "staff", "inventory",
        name="import_type_enum", create_type=False,
    )
    import_type_enum.create(op.get_bind(), checkfirst=True)

    import_format_enum = postgresql.ENUM(
        "xlsx", "csv", "json",
        name="import_format_enum", create_type=False,
    )
    import_format_enum.create(op.get_bind(), checkfirst=True)

    import_status_enum = postgresql.ENUM(
        "pending", "completed", "partial", "failed",
        name="import_status_enum", create_type=False,
    )
    import_status_enum.create(op.get_bind(), checkfirst=True)

    # ── 2. users ────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("role", postgresql.ENUM("owner", "moderator", "staff", "technician", "client", name="user_role_enum", create_type=False), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.Column("must_change_password", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_role", "users", ["role"])

    # ── 3. clients ──────────────────────────────────────────────────────────────
    op.create_table(
        "clients",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("contact_name", sa.String(length=120), nullable=True),
        sa.Column("contact_email", sa.String(length=255), nullable=True),
        sa.Column("contact_phone", sa.String(length=20), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("state", sa.String(length=100), nullable=True),
        sa.Column("pincode", sa.String(length=10), nullable=True),
        sa.Column("gst_number", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_clients_name", "clients", ["name"])

    # ── 4. sites ────────────────────────────────────────────────────────────────
    op.create_table(
        "sites",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("state", sa.String(length=100), nullable=True),
        sa.Column("pincode", sa.String(length=10), nullable=True),
        sa.Column("latitude", sa.Numeric(precision=10, scale=7), nullable=True),
        sa.Column("longitude", sa.Numeric(precision=10, scale=7), nullable=True),
        sa.Column("geo_fence_radius_m", sa.Integer(), server_default="200", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── 5. dg_sets ──────────────────────────────────────────────────────────────
    op.create_table(
        "dg_sets",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("serial_number", sa.String(length=100), nullable=False),
        sa.Column("make", sa.String(length=100), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("capacity_kva", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("installation_date", sa.Date(), nullable=True),
        sa.Column("last_service_date", sa.Date(), nullable=True),
        sa.Column("next_service_date", sa.Date(), nullable=True),
        sa.Column("amc_start_date", sa.Date(), nullable=True),
        sa.Column("amc_end_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("serial_number"),
    )

    # ── 6. inventory ────────────────────────────────────────────────────────────
    op.create_table(
        "inventory",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("part_number", sa.String(length=100), nullable=True),
        sa.Column("barcode", sa.String(length=100), nullable=True),
        sa.Column("serial_number", sa.String(length=100), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("quantity", sa.Integer(), server_default="1", nullable=False),
        sa.Column("unit", sa.String(length=20), nullable=True),
        sa.Column("status", postgresql.ENUM(
            "available", "in_field", "under_repair", "retired",
            name="inventory_status_enum", create_type=False,
        ), nullable=False, server_default="available"),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("assigned_to", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("unit_cost", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.ForeignKeyConstraint(["assigned_to"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_inventory_barcode", "inventory", ["barcode"])
    op.create_index("ix_inventory_serial_number", "inventory", ["serial_number"])
    op.create_index("ix_inventory_status", "inventory", ["status"])

    # ── 7. ticket_technicians (association) ─────────────────────────────────────
    op.create_table(
        "ticket_technicians",
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("ticket_id", "user_id"),
    )

    # ── 8. tickets ───────────────────────────────────────────────────────────────
    op.create_table(
        "tickets",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("reference_no", sa.String(length=50), nullable=False),
        sa.Column("dg_set_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reported_issue", sa.Text(), nullable=False),
        sa.Column("status", postgresql.ENUM(
            "open", "assigned", "in_progress", "pending_parts", "resolved", "closed", "cancelled",
            name="ticket_status_enum", create_type=False,
        ), nullable=False, server_default="open"),
        sa.Column("priority", postgresql.ENUM(
            "low", "medium", "high", "critical",
            name="ticket_priority_enum", create_type=False,
        ), nullable=False, server_default="medium"),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["dg_set_id"], ["dg_sets.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reference_no"),
    )
    op.create_foreign_key(
        "fk_ticket_technicians_ticket",
        "ticket_technicians", "tickets",
        ["ticket_id"], ["id"], ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_ticket_technicians_user",
        "ticket_technicians", "users",
        ["user_id"], ["id"], ondelete="CASCADE",
    )

    # ── 9. ticket_status_history ─────────────────────────────────────────────────
    op.create_table(
        "ticket_status_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("changed_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("from_status", sa.String(length=50), nullable=True),
        sa.Column("to_status", sa.String(length=50), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["changed_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── 10. ticket_photos ────────────────────────────────────────────────────────
    op.create_table(
        "ticket_photos",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("photo_type", postgresql.ENUM(
            "before", "after", "signature",
            name="photo_type_enum", create_type=False,
        ), nullable=False),
        sa.Column("s3_key", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── 11. attendance ────────────────────────────────────────────────────────────
    op.create_table(
        "attendance",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("punch_in_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("punch_out_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("punch_in_lat", sa.Numeric(precision=10, scale=7), nullable=True),
        sa.Column("punch_in_lon", sa.Numeric(precision=10, scale=7), nullable=True),
        sa.Column("punch_out_lat", sa.Numeric(precision=10, scale=7), nullable=True),
        sa.Column("punch_out_lon", sa.Numeric(precision=10, scale=7), nullable=True),
        sa.Column("selfie_key", sa.String(length=512), nullable=True),
        sa.Column("liveness_score", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("status", postgresql.ENUM(
            "pending", "approved", "rejected", "flagged",
            name="attendance_status_enum", create_type=False,
        ), nullable=False, server_default="pending"),
        sa.Column("flag_reason", sa.String(length=255), nullable=True),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_attendance_user_date", "attendance", ["user_id", "punch_in_time"])

    # ── 12. expenses ──────────────────────────────────────────────────────────────
    op.create_table(
        "expenses",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("submitted_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="INR", nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("receipt_key", sa.String(length=512), nullable=True),
        sa.Column("status", postgresql.ENUM(
            "pending", "approved", "rejected", "reimbursed",
            name="expense_status_enum", create_type=False,
        ), nullable=False, server_default="pending"),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["submitted_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── 13. tenders ───────────────────────────────────────────────────────────────
    op.create_table(
        "tenders",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("reference_no", sa.String(length=100), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", postgresql.ENUM(
            "draft", "submitted", "under_review", "won", "lost", "cancelled",
            name="tender_status_enum", create_type=False,
        ), nullable=False, server_default="draft"),
        sa.Column("estimated_value", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("submission_deadline", sa.Date(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reference_no"),
    )

    # ── 14. audit_logs ────────────────────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("resource_type", sa.String(length=100), nullable=True),
        sa.Column("resource_id", sa.String(length=100), nullable=True),
        sa.Column("old_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("new_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_actor", "audit_logs", ["actor_id"])
    op.create_index("ix_audit_logs_resource", "audit_logs", ["resource_type", "resource_id"])

    # ── 15. bulk_import_logs ──────────────────────────────────────────────────────
    op.create_table(
        "bulk_import_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("imported_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("import_type", postgresql.ENUM(
            "staff", "inventory",
            name="import_type_enum", create_type=False,
        ), nullable=False),
        sa.Column("file_format", postgresql.ENUM(
            "xlsx", "csv", "json",
            name="import_format_enum", create_type=False,
        ), nullable=False),
        sa.Column("original_filename", sa.String(length=512), nullable=True),
        sa.Column("total_rows", sa.Integer(), server_default="0", nullable=False),
        sa.Column("success_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failure_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("status", postgresql.ENUM(
            "pending", "completed", "partial", "failed",
            name="import_status_enum", create_type=False,
        ), nullable=False, server_default="pending"),
        sa.Column("error_details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["imported_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bulk_import_logs_imported_by", "bulk_import_logs", ["imported_by"])
    op.create_index("ix_bulk_import_logs_created_at", "bulk_import_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("bulk_import_logs")
    op.drop_table("audit_logs")
    op.drop_table("tenders")
    op.drop_table("expenses")
    op.drop_table("attendance")
    op.drop_table("ticket_photos")
    op.drop_table("ticket_status_history")
    op.drop_table("ticket_technicians")
    op.drop_table("tickets")
    op.drop_table("inventory")
    op.drop_table("dg_sets")
    op.drop_table("sites")
    op.drop_table("clients")
    op.drop_table("users")

    for enum_name in [
        "import_status_enum", "import_format_enum", "import_type_enum",
        "tender_status_enum", "inventory_status_enum", "photo_type_enum",
        "ticket_priority_enum", "ticket_status_enum", "expense_status_enum",
        "attendance_status_enum", "user_role_enum",
    ]:
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
