"""fix_advance_payments_updated_at

Adds missing updated_at column to advance_payments table.

Revision ID: 0003_fix_advance_payments_updated_at
Revises: 0002_fix_schema_gaps
Create Date: 2026-03-27

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0003_fix_adv_pay'
down_revision: Union[str, None] = '0002_fix_schema_gaps'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'advance_payments',
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column('advance_payments', 'updated_at')
