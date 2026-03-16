from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.expense import Expense, ExpenseStatus
from app.repositories.base import BaseRepository


class ExpenseRepository(BaseRepository[Expense]):
    model = Expense

    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def list_for_user(self, user_id: UUID, skip: int = 0, limit: int = 50) -> list[Expense]:
        return (
            self.db.query(Expense)
            .filter(Expense.submitted_by == user_id, Expense.is_deleted.is_(False))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def list_pending(self, skip: int = 0, limit: int = 50) -> list[Expense]:
        return (
            self.db.query(Expense)
            .filter(Expense.status == ExpenseStatus.SUBMITTED, Expense.is_deleted.is_(False))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def top_pending(self, limit: int = 5) -> list[Expense]:
        return (
            self.db.query(Expense)
            .filter(Expense.status == ExpenseStatus.SUBMITTED, Expense.is_deleted.is_(False))
            .order_by(Expense.amount.desc())
            .limit(limit)
            .all()
        )
