from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from app.models.payroll import AdvancePayment, SalaryRecord
from app.repositories.base import BaseRepository


class SalaryRepository(BaseRepository[SalaryRecord]):
    model = SalaryRecord

    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def get_by_user_month(
        self, user_id: UUID, year: int, month: int
    ) -> SalaryRecord | None:
        return (
            self.db.query(SalaryRecord)
            .filter(
                SalaryRecord.user_id == user_id,
                SalaryRecord.year == year,
                SalaryRecord.month == month,
            )
            .first()
        )

    def list_for_user(self, user_id: UUID) -> list[SalaryRecord]:
        return (
            self.db.query(SalaryRecord)
            .options(joinedload(SalaryRecord.recorder))
            .filter(SalaryRecord.user_id == user_id)
            .order_by(SalaryRecord.year.desc(), SalaryRecord.month.desc())
            .all()
        )

    def list_all(self, skip: int = 0, limit: int = 200) -> list[SalaryRecord]:
        return (
            self.db.query(SalaryRecord)
            .options(
                joinedload(SalaryRecord.user),
                joinedload(SalaryRecord.recorder),
            )
            .order_by(SalaryRecord.year.desc(), SalaryRecord.month.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )


class AdvancePaymentRepository(BaseRepository[AdvancePayment]):
    model = AdvancePayment

    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def list_for_user(self, user_id: UUID) -> list[AdvancePayment]:
        return (
            self.db.query(AdvancePayment)
            .options(joinedload(AdvancePayment.giver))
            .filter(AdvancePayment.user_id == user_id)
            .order_by(AdvancePayment.payment_date.desc())
            .all()
        )

    def list_all(self, skip: int = 0, limit: int = 200) -> list[AdvancePayment]:
        return (
            self.db.query(AdvancePayment)
            .options(
                joinedload(AdvancePayment.user),
                joinedload(AdvancePayment.giver),
            )
            .order_by(AdvancePayment.payment_date.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def sum_for_user_year(self, user_id: UUID, year: int) -> Decimal:
        """Total advances given to a user in the given calendar year."""
        from sqlalchemy import extract, func

        result = (
            self.db.query(func.coalesce(func.sum(AdvancePayment.amount), Decimal("0.00")))
            .filter(
                AdvancePayment.user_id == user_id,
                extract("year", AdvancePayment.payment_date) == year,
            )
            .scalar()
        )
        return Decimal(str(result or "0.00"))
