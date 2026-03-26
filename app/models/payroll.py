from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import DECIMAL, Date, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import UUIDMixin, TimestampMixin


class SalaryStatus(str, enum.Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    PARTIAL = "PARTIAL"
    ON_HOLD = "ON_HOLD"


class SalaryRecord(Base, UUIDMixin, TimestampMixin):
    """
    Monthly salary record for a staff/moderator user.

    One record per user per (year, month). Tracks the gross salary, any
    advance deducted, net payable and current payment status.
    """

    __tablename__ = "salary_records"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)  # 1–12

    # Salary components
    gross_salary: Mapped[Decimal] = mapped_column(DECIMAL(12, 2), nullable=False)
    advance_deducted: Mapped[Decimal] = mapped_column(
        DECIMAL(12, 2), nullable=False, default=Decimal("0.00")
    )
    net_payable: Mapped[Decimal] = mapped_column(DECIMAL(12, 2), nullable=False)

    status: Mapped[SalaryStatus] = mapped_column(
        Enum(SalaryStatus, name="salary_status_enum", create_type=False),
        nullable=False,
        default=SalaryStatus.PENDING,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Who recorded / last updated this entry
    recorded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user: Mapped["User | None"] = relationship(
        "User", foreign_keys=[user_id], lazy="select"
    )
    recorder: Mapped["User | None"] = relationship(
        "User", foreign_keys=[recorded_by], lazy="select"
    )


class AdvancePayment(Base, UUIDMixin, TimestampMixin):
    """
    An advance salary / cash advance given to a staff/moderator user.

    Records the amount, the date the cash was handed over, and the owner
    or moderator who authorised / processed the payment.
    """

    __tablename__ = "advance_payments"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(DECIMAL(12, 2), nullable=False)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # The owner/moderator who processed the payment
    given_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    # Optional: link the advance to a salary record (for deduction tracking)
    salary_record_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("salary_records.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    user: Mapped["User | None"] = relationship(
        "User", foreign_keys=[user_id], lazy="select"
    )
    giver: Mapped["User | None"] = relationship(
        "User", foreign_keys=[given_by], lazy="select"
    )
    salary_record: Mapped["SalaryRecord | None"] = relationship(
        "SalaryRecord", foreign_keys=[salary_record_id], lazy="select"
    )
