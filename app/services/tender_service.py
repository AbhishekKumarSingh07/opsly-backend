from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.models.tender import (
    Tender,
    TenderDocument,
    TenderMilestone,
    TenderStatus,
)
from app.models.user import User
from app.repositories.tender_repo import TenderRepository
from app.schemas.tender import MilestoneCreate, MilestoneUpdate, TenderCreate, TenderStatusUpdate

# ─── Tender state machine ─────────────────────────────────────────────────────

TENDER_TRANSITIONS: dict[TenderStatus, list[TenderStatus]] = {
    TenderStatus.BIDDING: [TenderStatus.WON, TenderStatus.LOST],
    TenderStatus.WON: [TenderStatus.PROCUREMENT],
    TenderStatus.LOST: [TenderStatus.BIDDING],  # Allow re-bidding
    TenderStatus.PROCUREMENT: [TenderStatus.INSTALLATION],
    TenderStatus.INSTALLATION: [TenderStatus.COMMISSIONING],
    TenderStatus.COMMISSIONING: [TenderStatus.INVOICED],
    TenderStatus.INVOICED: [TenderStatus.CLOSED],
    TenderStatus.CLOSED: [],
}


def _generate_tender_reference(db: Session) -> str:
    from sqlalchemy import func
    year = datetime.now(timezone.utc).year
    prefix = f"TND-{year}-"
    count = (
        db.query(func.count(Tender.id))
        .filter(Tender.reference_no.like(f"{prefix}%"))
        .scalar()
        or 0
    )
    return f"{prefix}{(count + 1):04d}"


class TenderService:
    """Business logic for tender lifecycle, milestones and documents."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = TenderRepository(db)

    def create_tender(self, payload: TenderCreate, created_by: User) -> Tender:
        """Create a new tender in BIDDING status."""
        tender = Tender(
            reference_no=_generate_tender_reference(self.db),
            title=payload.title,
            client_name=payload.client_name,
            client_contact=payload.client_contact,
            status=TenderStatus.BIDDING,
            bid_amount=payload.bid_amount,
            bid_submission_date=payload.bid_submission_date,
            expected_start_date=payload.expected_start_date,
            expected_end_date=payload.expected_end_date,
            notes=payload.notes,
            created_by=created_by.id,
        )
        return self.repo.create(tender)

    def update_status(self, tender_id: UUID, payload: TenderStatusUpdate, user: User) -> Tender:
        """Transition tender to a new status following the state machine."""
        tender = self._get_or_raise(tender_id)
        allowed = TENDER_TRANSITIONS.get(tender.status, [])
        if payload.new_status not in allowed:
            raise BusinessRuleError(
                "INVALID_TENDER_TRANSITION",
                f"Cannot transition from {tender.status.value} to {payload.new_status.value}.",
            )
        tender.status = payload.new_status
        if payload.notes:
            tender.notes = (tender.notes or "") + f"\n[{user.email}] {payload.notes}"
        return self.repo.save(tender)

    def add_milestone(self, tender_id: UUID, payload: MilestoneCreate, user: User) -> TenderMilestone:
        """Add a payment milestone to a tender."""
        tender = self._get_or_raise(tender_id)
        milestone = TenderMilestone(
            tender_id=tender.id,
            name=payload.name,
            description=payload.description,
            sequence_no=payload.sequence_no,
            due_date=payload.due_date,
            payment_percentage=payload.payment_percentage,
            payment_amount=payload.payment_amount,
        )
        return self.repo.add_milestone(milestone)

    def update_milestone(self, milestone_id: UUID, payload: MilestoneUpdate, user: User) -> TenderMilestone:
        """Update milestone completion/payment data."""
        milestone = self.repo.get_milestone(milestone_id)
        if not milestone:
            raise NotFoundError("TenderMilestone", str(milestone_id))
        if payload.actual_completion_date is not None:
            milestone.actual_completion_date = payload.actual_completion_date
        if payload.payment_status is not None:
            milestone.payment_status = payload.payment_status
        if payload.payment_amount is not None:
            milestone.payment_amount = payload.payment_amount
        if payload.proof_document_url is not None:
            milestone.proof_document_url = payload.proof_document_url
        self.db.flush()
        self.db.refresh(milestone)
        return milestone

    def attach_document(
        self, tender_id: UUID, document_type: str, filename: str, s3_url: str, uploader: User
    ) -> TenderDocument:
        """Attach a versioned document to a tender."""
        tender = self._get_or_raise(tender_id)
        doc = TenderDocument(
            tender_id=tender.id,
            document_type=document_type,
            filename=filename,
            s3_url=s3_url,
            uploaded_by=uploader.id,
            uploaded_at=datetime.now(timezone.utc),
            version=len(tender.documents) + 1,
        )
        return self.repo.add_document(doc)

    def _get_or_raise(self, tender_id: UUID) -> Tender:
        tender = self.repo.get_by_id(tender_id)
        if not tender or tender.is_deleted:
            raise NotFoundError("Tender", str(tender_id))
        return tender
