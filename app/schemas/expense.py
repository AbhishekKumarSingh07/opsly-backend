from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.expense import ExpenseStatus


class ExpenseCreate(BaseModel):
    """Request body for submitting an expense."""

    model_config = ConfigDict(from_attributes=True)

    ticket_id: UUID | None = None
    tender_id: UUID | None = None
    category: str
    description: str | None = None
    amount: Decimal
    receipt_url: str | None = None


class ExpenseReview(BaseModel):
    """Request body for approving or rejecting an expense."""

    model_config = ConfigDict(from_attributes=True)

    status: ExpenseStatus
    review_notes: str | None = None


class ExpenseResponse(BaseModel):
    """Expense response model."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    submitted_by: UUID
    ticket_id: UUID | None
    tender_id: UUID | None
    category: str
    description: str | None
    amount: Decimal
    receipt_url: str | None
    status: ExpenseStatus
    reviewed_by: UUID | None
    reviewed_at: datetime | None
    review_notes: str | None
    created_at: datetime
