"""add_payroll_tables

Revision ID: a3f9c2d81b55
Revises: ecbda1edd94d
Create Date: 2026-03-25 10:00:00.000000

Adds:
  - salary_records  — monthly salary tracking per staff/moderator
  - advance_payments — advance salary / cash payments given to staff
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "a3f9c2d81b55"
down_revision = "ecbda1edd94d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── salary_status enum ───────────────────────────────────────────────────
    # We must use raw SQL with IF NOT EXISTS because:
    #   1. env.py imports all models, registering salary_status_enum in metadata
    #   2. SQLAlchemy fires a before_create event during op.create_table that
    #      tries to CREATE the type again — causing DuplicateObject.
    # By creating it here with IF NOT EXISTS and using create_type=False on the
    # column definition, we own the lifecycle fully.
    op.execute(
        "DO $$ BEGIN "
        "  CREATE TYPE salary_status_enum AS ENUM ('PENDING', 'PAID', 'PARTIAL', 'ON_HOLD'); "
        "EXCEPTION WHEN duplicate_object THEN null; "
        "END $$;"
    )


    # ── salary_records ───────────────────────────────────────────────────────
    op.create_table(
        "salary_records",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("gross_salary", sa.DECIMAL(12, 2), nullable=False),
        sa.Column(
            "advance_deducted",
            sa.DECIMAL(12, 2),
            nullable=False,
            server_default="0.00",
        ),
        sa.Column("net_payable", sa.DECIMAL(12, 2), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "PENDING", "PAID", "PARTIAL", "ON_HOLD",
                name="salary_status_enum",
                create_type=False,  # type already created above via DO $$ ... $$
            ),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("recorded_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recorded_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "year", "month", name="uq_salary_user_year_month"),
    )
    op.create_index("ix_salary_records_user_id", "salary_records", ["user_id"])
    op.create_index(
        "ix_salary_records_year_month", "salary_records", ["year", "month"]
    )

    # ── advance_payments ─────────────────────────────────────────────────────
    op.create_table(
        "advance_payments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.DECIMAL(12, 2), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column("given_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("salary_record_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["given_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["salary_record_id"], ["salary_records.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_advance_payments_user_id", "advance_payments", ["user_id"])
    op.create_index(
        "ix_advance_payments_payment_date", "advance_payments", ["payment_date"]
    )


def downgrade() -> None:
    op.drop_table("advance_payments")
    op.drop_table("salary_records")
    sa.Enum(name="salary_status_enum").drop(op.get_bind(), checkfirst=True)
