from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.tender import MilestonePaymentStatus, TenderStatus


class TenderCreate(BaseModel):
    """Request body for creating a new tender."""

    model_config = ConfigDict(from_attributes=True)

    title: str
    client_name: str
    client_contact: str | None = None
    bid_amount: Decimal | None = None
    bid_submission_date: date | None = None
    expected_start_date: date | None = None
    expected_end_date: date | None = None
    notes: str | None = None


class TenderStatusUpdate(BaseModel):
    """Request body for updating tender status."""

    model_config = ConfigDict(from_attributes=True)

    new_status: TenderStatus
    notes: str | None = None


class MilestoneCreate(BaseModel):
    """Request body for adding a milestone to a tender."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    description: str | None = None
    sequence_no: int = 1
    due_date: date | None = None
    payment_percentage: Decimal = Decimal("0")
    payment_amount: Decimal | None = None


class MilestoneUpdate(BaseModel):
    """Request body for updating a tender milestone."""

    model_config = ConfigDict(from_attributes=True)

    actual_completion_date: date | None = None
    payment_status: MilestonePaymentStatus | None = None
    payment_amount: Decimal | None = None
    proof_document_url: str | None = None


class TenderMilestoneResponse(BaseModel):
    """Tender milestone response model."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tender_id: UUID
    name: str
    description: str | None
    sequence_no: int
    due_date: date | None
    actual_completion_date: date | None
    payment_percentage: Decimal
    payment_amount: Decimal | None
    payment_status: MilestonePaymentStatus
    proof_document_url: str | None


class TenderDocumentResponse(BaseModel):
    """Tender document response model."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tender_id: UUID
    document_type: str
    filename: str
    s3_url: str
    version: int
    uploaded_by: UUID
    uploaded_at: datetime


class TenderResponse(BaseModel):
    """Full tender response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    reference_no: str
    title: str
    client_name: str
    client_contact: str | None
    status: TenderStatus
    bid_amount: Decimal | None
    awarded_amount: Decimal | None
    bid_submission_date: date | None
    expected_start_date: date | None
    expected_end_date: date | None
    notes: str | None
    created_by: UUID
    created_at: datetime
    milestones: list[TenderMilestoneResponse] = []
    documents: list[TenderDocumentResponse] = []
