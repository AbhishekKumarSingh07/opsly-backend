from __future__ import annotations

import calendar
import logging
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError
from app.models.payroll import AdvancePayment, SalaryRecord, SalaryStatus
from app.models.user import User, UserRole
from app.repositories.payroll_repo import AdvancePaymentRepository, SalaryRepository
from app.repositories.user_repo import UserRepository
from app.schemas.payroll import (
    AdvancePaymentCreate,
    AdvancePaymentResponse,
    SalaryRecordCreate,
    SalaryRecordResponse,
    SalaryRecordUpdate,
    StaffPayrollSummary,
)

logger = logging.getLogger("opsly.payroll")


class PayrollService:
    """Business logic for salary records and advance payments."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.salary_repo = SalaryRepository(db)
        self.advance_repo = AdvancePaymentRepository(db)
        self.user_repo = UserRepository(db)

    # ─── Salary Records ───────────────────────────────────────────────────────

    def create_salary_record(
        self, recorder: User, payload: SalaryRecordCreate
    ) -> SalaryRecord:
        """
        Create a monthly salary record for a user.

        - Owner only.
        - Raises 409 if a record already exists for that user/year/month.
        - net_payable is computed automatically as gross - advance_deducted.
        """
        if recorder.role != UserRole.owner:
            raise PermissionDeniedError("Only the owner can manage salary records.")

        target = self.user_repo.get_by_id(payload.user_id)
        if not target:
            raise NotFoundError("User", str(payload.user_id))

        if target.role == UserRole.owner:
            raise PermissionDeniedError("Salary records cannot be created for the owner.")

        existing = self.salary_repo.get_by_user_month(
            payload.user_id, payload.year, payload.month
        )
        if existing:
            raise ConflictError(
                f"A salary record for {target.name} in "
                f"{calendar.month_name[payload.month]} {payload.year} already exists. "
                "Use PATCH to update it."
            )

        net = payload.gross_salary - payload.advance_deducted
        record = SalaryRecord(
            user_id=payload.user_id,
            year=payload.year,
            month=payload.month,
            gross_salary=payload.gross_salary,
            advance_deducted=payload.advance_deducted,
            net_payable=net,
            status=payload.status,
            notes=payload.notes,
            recorded_by=recorder.id,
            paid_at=payload.paid_at,
        )
        logger.info(
            "Salary record created for user %s %s/%s by owner %s",
            payload.user_id, payload.month, payload.year, recorder.id,
        )
        return self.salary_repo.create(record)

    def update_salary_record(
        self, recorder: User, salary_id: UUID, payload: SalaryRecordUpdate
    ) -> SalaryRecord:
        """Partially update a salary record. Owner only."""
        if recorder.role != UserRole.owner:
            raise PermissionDeniedError("Only the owner can update salary records.")

        record = self.salary_repo.get_by_id(salary_id)
        if not record:
            raise NotFoundError("SalaryRecord", str(salary_id))

        if payload.gross_salary is not None:
            record.gross_salary = payload.gross_salary
        if payload.advance_deducted is not None:
            record.advance_deducted = payload.advance_deducted
        # Recompute net_payable whenever gross or advance changes
        record.net_payable = record.gross_salary - record.advance_deducted
        if payload.status is not None:
            record.status = payload.status
            if payload.status == SalaryStatus.PAID and record.paid_at is None:
                record.paid_at = datetime.now(timezone.utc)
        if payload.notes is not None:
            record.notes = payload.notes
        if payload.paid_at is not None:
            record.paid_at = payload.paid_at

        return self.salary_repo.save(record)

    def list_salary_records_for_user(self, user_id: UUID) -> list[SalaryRecord]:
        return self.salary_repo.list_for_user(user_id)

    def list_all_salary_records(self, skip: int = 0, limit: int = 200) -> list[SalaryRecord]:
        return self.salary_repo.list_all(skip=skip, limit=limit)

    # ─── Advance Payments ─────────────────────────────────────────────────────

    def create_advance_payment(
        self, giver: User, payload: AdvancePaymentCreate
    ) -> AdvancePayment:
        """
        Record a cash advance given to a staff/moderator.

        - Owner can give advances to any staff/moderator.
        - Moderator can only give advances to staff.
        """
        target = self.user_repo.get_by_id(payload.user_id)
        if not target:
            raise NotFoundError("User", str(payload.user_id))

        if target.role == UserRole.owner:
            raise PermissionDeniedError("Advance payments cannot be given to the owner.")

        if giver.role == UserRole.moderator and target.role != UserRole.staff:
            raise PermissionDeniedError(
                "Moderators can only give advances to staff members."
            )

        if giver.role not in (UserRole.owner, UserRole.moderator):
            raise PermissionDeniedError(
                "Only owner or moderator can process advance payments."
            )

        # Optionally validate salary_record_id
        if payload.salary_record_id:
            record = self.salary_repo.get_by_id(payload.salary_record_id)
            if not record:
                raise NotFoundError("SalaryRecord", str(payload.salary_record_id))
            if str(record.user_id) != str(payload.user_id):
                raise PermissionDeniedError(
                    "The salary record does not belong to the specified user."
                )

        advance = AdvancePayment(
            user_id=payload.user_id,
            amount=payload.amount,
            payment_date=payload.payment_date,
            reason=payload.reason,
            given_by=giver.id,
            salary_record_id=payload.salary_record_id,
        )
        logger.info(
            "Advance payment of %s recorded for user %s by %s",
            payload.amount, payload.user_id, giver.id,
        )
        return self.advance_repo.create(advance)

    def list_advances_for_user(self, user_id: UUID) -> list[AdvancePayment]:
        return self.advance_repo.list_for_user(user_id)

    def list_all_advances(self, skip: int = 0, limit: int = 200) -> list[AdvancePayment]:
        return self.advance_repo.list_all(skip=skip, limit=limit)

    # ─── Combined Payroll Summary ─────────────────────────────────────────────

    def get_payroll_summary(self) -> list[StaffPayrollSummary]:
        """
        Return a combined payroll snapshot for all staff + moderators.
        Used by the owner's staff management page.
        """
        from datetime import datetime

        year = datetime.now(timezone.utc).year
        users = self.user_repo.list_all()

        summaries: list[StaffPayrollSummary] = []
        for u in users:
            if u.role == UserRole.owner:
                continue  # Owner is excluded

            salary_records = self.salary_repo.list_for_user(u.id)
            advances = self.advance_repo.list_for_user(u.id)
            total_advances_ytd = self.advance_repo.sum_for_user_year(u.id, year)

            # Latest salary record (sorted desc already)
            latest = salary_records[0] if salary_records else None

            summaries.append(
                StaffPayrollSummary(
                    user_id=u.id,
                    user_name=u.name,
                    user_role=u.role.value,
                    latest_salary_status=latest.status if latest else None,
                    latest_salary_month=(
                        f"{calendar.month_name[latest.month]} {latest.year}"
                        if latest
                        else None
                    ),
                    latest_net_payable=latest.net_payable if latest else None,
                    total_advances_ytd=total_advances_ytd,
                    salary_records=[
                        SalaryRecordResponse.from_orm_with_relations(r)
                        for r in salary_records
                    ],
                    advance_payments=[
                        AdvancePaymentResponse.from_orm_with_relations(a)
                        for a in advances
                    ],
                )
            )
        return summaries
