from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, NotFoundError, PermissionDeniedError
from app.models.expense import Expense, ExpenseStatus
from app.models.user import User, UserRole
from app.repositories.expense_repo import ExpenseRepository
from app.schemas.expense import ExpenseCreate, ExpenseReview


class ExpenseService:
    """Business logic for expense claim submission and review."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = ExpenseRepository(db)

    def create_expense(self, payload: ExpenseCreate, submitted_by: User) -> Expense:
        """Submit a new expense claim."""
        expense = Expense(
            submitted_by=submitted_by.id,
            ticket_id=payload.ticket_id,
            tender_id=payload.tender_id,
            category=payload.category,
            description=payload.description,
            amount=payload.amount,
            receipt_url=payload.receipt_url,
            status=ExpenseStatus.SUBMITTED,
        )
        return self.repo.create(expense)

    def review_expense(self, expense_id: UUID, payload: ExpenseReview, reviewer: User) -> Expense:
        """Approve or reject an expense claim. Only moderator/owner can review."""
        if reviewer.role == UserRole.staff:
            raise PermissionDeniedError("Staff cannot review expenses.")

        expense = self.repo.get_by_id(expense_id)
        if not expense or expense.is_deleted:
            raise NotFoundError("Expense", str(expense_id))

        if expense.status not in (ExpenseStatus.SUBMITTED, ExpenseStatus.DRAFT):
            raise BusinessRuleError(
                "EXPENSE_NOT_REVIEWABLE",
                f"Expense is already {expense.status.value}.",
            )

        expense.status = payload.status
        expense.reviewed_by = reviewer.id
        expense.reviewed_at = datetime.now(timezone.utc)
        expense.review_notes = payload.review_notes
        return self.repo.save(expense)
