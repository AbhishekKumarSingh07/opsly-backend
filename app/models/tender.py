from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import DECIMAL, Date, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import AuditMixin, UUIDMixin, TimestampMixin


class TenderStatus(str, enum.Enum):
    BIDDING = "BIDDING"
    WON = "WON"
    LOST = "LOST"
    PROCUREMENT = "PROCUREMENT"
    INSTALLATION = "INSTALLATION"
    COMMISSIONING = "COMMISSIONING"
    INVOICED = "INVOICED"
    CLOSED = "CLOSED"


class MilestonePaymentStatus(str, enum.Enum):
    PENDING = "PENDING"
    PARTIAL = "PARTIAL"
    RECEIVED = "RECEIVED"


class Tender(Base, AuditMixin):
    """Represents a tender / project bid and its lifecycle."""

    __tablename__ = "tenders"

    reference_no: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    client_name: Mapped[str] = mapped_column(String(255), nullable=False)
    client_contact: Mapped[str | None] = mapped_column(String(255), nullable=True)

    status: Mapped[TenderStatus] = mapped_column(
        Enum(TenderStatus, name="tender_status_enum"),
        default=TenderStatus.BIDDING,
        nullable=False,
    )

    bid_amount: Mapped[Decimal | None] = mapped_column(DECIMAL(14, 2), nullable=True)
    awarded_amount: Mapped[Decimal | None] = mapped_column(DECIMAL(14, 2), nullable=True)
    bid_submission_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expected_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expected_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    milestones: Mapped[list["TenderMilestone"]] = relationship(
        "TenderMilestone", back_populates="tender", lazy="select", cascade="all, delete-orphan"
    )
    documents: Mapped[list["TenderDocument"]] = relationship(
        "TenderDocument", back_populates="tender", lazy="select", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Tender ref={self.reference_no} status={self.status}>"


class TenderMilestone(Base, UUIDMixin, TimestampMixin):
    """A payment milestone within a tender."""

    __tablename__ = "tender_milestones"

    tender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenders.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_completion_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    payment_percentage: Mapped[Decimal] = mapped_column(DECIMAL(5, 2), nullable=False, default=Decimal("0"))
    payment_amount: Mapped[Decimal | None] = mapped_column(DECIMAL(14, 2), nullable=True)
    payment_status: Mapped[MilestonePaymentStatus] = mapped_column(
        Enum(MilestonePaymentStatus, name="milestone_payment_status_enum"),
        default=MilestonePaymentStatus.PENDING,
        nullable=False,
    )
    proof_document_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    tender: Mapped["Tender | None"] = relationship("Tender", back_populates="milestones")

    def __repr__(self) -> str:
        return f"<TenderMilestone tender={self.tender_id} name={self.name}>"


class TenderDocument(Base, UUIDMixin):
    """Versioned document attached to a tender."""

    __tablename__ = "tender_documents"

    tender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenders.id"), nullable=False, index=True
    )
    document_type: Mapped[str] = mapped_column(String(100), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    s3_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    tender: Mapped["Tender | None"] = relationship("Tender", back_populates="documents")

    def __repr__(self) -> str:
        return f"<TenderDocument tender={self.tender_id} file={self.filename}>"
