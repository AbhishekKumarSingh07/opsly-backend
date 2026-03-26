from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.payroll import SalaryStatus


# ─── Salary Record Schemas ────────────────────────────────────────────────────

class SalaryRecordCreate(BaseModel):
    """Request body to create or update a monthly salary record."""

    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    year: int = Field(..., ge=2020, le=2099)
    month: int = Field(..., ge=1, le=12)
    gross_salary: Decimal = Field(..., ge=0)
    advance_deducted: Decimal = Field(default=Decimal("0.00"), ge=0)
    status: SalaryStatus = SalaryStatus.PENDING
    notes: str | None = None
    paid_at: datetime | None = None


class SalaryRecordUpdate(BaseModel):
    """Partial update for a salary record (status, notes, paid_at)."""

    model_config = ConfigDict(from_attributes=True)

    gross_salary: Decimal | None = None
    advance_deducted: Decimal | None = None
    status: SalaryStatus | None = None
    notes: str | None = None
    paid_at: datetime | None = None


class SalaryRecordResponse(BaseModel):
    """Salary record response returned to owner."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    user_name: str | None = None
    user_role: str | None = None
    year: int
    month: int
    gross_salary: Decimal
    advance_deducted: Decimal
    net_payable: Decimal
    status: SalaryStatus
    notes: str | None
    recorded_by: UUID
    recorder_name: str | None = None
    paid_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_orm_with_relations(cls, record: object) -> "SalaryRecordResponse":
        obj = cls.model_validate(record)
        user = getattr(record, "user", None)
        if user:
            obj.user_name = getattr(user, "name", None)
            obj.user_role = getattr(user, "role", None)
            if obj.user_role and hasattr(obj.user_role, "value"):
                obj.user_role = obj.user_role.value
        recorder = getattr(record, "recorder", None)
        if recorder:
            obj.recorder_name = getattr(recorder, "name", None)
        return obj


# ─── Advance Payment Schemas ──────────────────────────────────────────────────

class AdvancePaymentCreate(BaseModel):
    """Request body to record an advance payment given to a staff/moderator."""

    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    amount: Decimal = Field(..., gt=0)
    payment_date: date
    reason: str | None = None
    salary_record_id: UUID | None = None


class AdvancePaymentResponse(BaseModel):
    """Advance payment response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    user_name: str | None = None
    amount: Decimal
    payment_date: date
    reason: str | None
    given_by: UUID
    given_by_name: str | None = None
    salary_record_id: UUID | None
    created_at: datetime

    @classmethod
    def from_orm_with_relations(cls, record: object) -> "AdvancePaymentResponse":
        obj = cls.model_validate(record)
        user = getattr(record, "user", None)
        if user:
            obj.user_name = getattr(user, "name", None)
        giver = getattr(record, "giver", None)
        if giver:
            obj.given_by_name = getattr(giver, "name", None)
        return obj


# ─── Staff Payroll Summary ────────────────────────────────────────────────────

class StaffPayrollSummary(BaseModel):
    """Combined payroll snapshot for one staff member (for owner list view)."""

    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    user_name: str
    user_role: str
    latest_salary_status: SalaryStatus | None = None
    latest_salary_month: str | None = None   # "March 2026"
    latest_net_payable: Decimal | None = None
    total_advances_ytd: Decimal = Decimal("0.00")
    salary_records: list[SalaryRecordResponse] = []
    advance_payments: list[AdvancePaymentResponse] = []
