from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    String,
    Table,
    Column,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import AuditMixin, UUIDMixin, TimestampMixin


class TicketStatus(str, enum.Enum):
    OPEN = "OPEN"
    ASSIGNED = "ASSIGNED"
    EN_ROUTE = "EN_ROUTE"
    IN_PROGRESS = "IN_PROGRESS"
    WAITING_FOR_PARTS = "WAITING_FOR_PARTS"
    COMPLETED = "COMPLETED"
    INVOICED = "INVOICED"
    CANCELLED = "CANCELLED"


class TicketPriority(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class PhotoType(str, enum.Enum):
    BEFORE = "BEFORE"
    AFTER = "AFTER"
    PART_NEW = "PART_NEW"
    PART_OLD = "PART_OLD"
    SITE = "SITE"


# Many-to-many: tickets <-> technicians (users)
ticket_technicians = Table(
    "ticket_technicians",
    Base.metadata,
    Column("ticket_id", UUID(as_uuid=True), ForeignKey("tickets.id"), primary_key=True),
    Column("user_id", UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True),
)


class Ticket(Base, AuditMixin):
    """Represents a field service / maintenance ticket."""

    __tablename__ = "tickets"

    reference_no: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    dg_set_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dg_sets.id", ondelete="SET NULL"), nullable=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    status: Mapped[TicketStatus] = mapped_column(
        Enum(TicketStatus, name="ticket_status_enum"),
        default=TicketStatus.OPEN,
        nullable=False,
    )
    priority: Mapped[TicketPriority] = mapped_column(
        Enum(TicketPriority, name="ticket_priority_enum"),
        default=TicketPriority.MEDIUM,
        nullable=False,
    )
    reported_issue: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    invoiced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    technicians: Mapped[list["User"]] = relationship(
        "User",
        secondary=ticket_technicians,
        back_populates="assigned_tickets",
        lazy="select",
    )
    creator: Mapped["User | None"] = relationship(
        "User",
        back_populates="created_tickets",
        foreign_keys=[created_by],
        lazy="select",
    )
    dg_set: Mapped["DGSet | None"] = relationship("DGSet", back_populates="tickets", lazy="select")
    status_history: Mapped[list["TicketStatusHistory"]] = relationship(
        "TicketStatusHistory", back_populates="ticket", lazy="select", cascade="all, delete-orphan"
    )
    photos: Mapped[list["TicketPhoto"]] = relationship(
        "TicketPhoto", back_populates="ticket", lazy="select", cascade="all, delete-orphan"
    )
    inventory_items: Mapped[list["InventoryItem"]] = relationship(
        "InventoryItem", back_populates="current_ticket", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Ticket ref={self.reference_no} status={self.status}>"


class TicketStatusHistory(Base, UUIDMixin):
    """Immutable log of every ticket status transition."""

    __tablename__ = "ticket_status_history"

    ticket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tickets.id"), nullable=False, index=True
    )
    from_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    to_status: Mapped[str] = mapped_column(String(50), nullable=False)
    changed_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    ticket: Mapped["Ticket | None"] = relationship("Ticket", back_populates="status_history")

    def __repr__(self) -> str:
        return f"<TicketStatusHistory {self.from_status}→{self.to_status}>"


class TicketPhoto(Base, UUIDMixin):
    """Photo attachments for a ticket (before/after/part/site)."""

    __tablename__ = "ticket_photos"

    ticket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tickets.id"), nullable=False, index=True
    )
    photo_type: Mapped[PhotoType] = mapped_column(
        Enum(PhotoType, name="photo_type_enum"), nullable=False
    )
    s3_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    gps_lat: Mapped[float | None] = mapped_column(nullable=True)
    gps_lng: Mapped[float | None] = mapped_column(nullable=True)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    ticket: Mapped["Ticket | None"] = relationship("Ticket", back_populates="photos")

    def __repr__(self) -> str:
        return f"<TicketPhoto ticket={self.ticket_id} type={self.photo_type}>"
