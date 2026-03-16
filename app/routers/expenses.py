from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db, require_role
from app.repositories.expense_repo import ExpenseRepository
from app.schemas.expense import ExpenseCreate, ExpenseResponse, ExpenseReview
from app.services.expense_service import ExpenseService

router = APIRouter(prefix="/expenses", tags=["Expenses"])


@router.post("/", response_model=ExpenseResponse)
def submit_expense(
    payload: ExpenseCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Submit a new expense claim.

    - Accessible by: all authenticated users.
    """
    service = ExpenseService(db)
    return service.create_expense(payload, current_user)


@router.get("/my", response_model=list[ExpenseResponse])
def my_expenses(
    skip: int = 0,
    limit: int = 50,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return the current user's expense claims.

    - Accessible by: all roles.
    """
    repo = ExpenseRepository(db)
    return repo.list_for_user(current_user.id, skip=skip, limit=limit)


@router.get("/pending", response_model=list[ExpenseResponse], dependencies=[Depends(require_role("owner", "moderator"))])
def pending_expenses(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """
    Return all submitted (pending review) expenses.

    - Accessible by: owner, moderator.
    """
    repo = ExpenseRepository(db)
    return repo.list_pending(skip=skip, limit=limit)


@router.patch("/{expense_id}/review", response_model=ExpenseResponse)
def review_expense(
    expense_id: UUID,
    payload: ExpenseReview,
    current_user=Depends(require_role("owner", "moderator")),
    db: Session = Depends(get_db),
):
    """
    Approve or reject an expense claim.

    - Accessible by: owner, moderator.
    """
    service = ExpenseService(db)
    return service.review_expense(expense_id, payload, current_user)
