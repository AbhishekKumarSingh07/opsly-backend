from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import UUIDMixin, TimestampMixin


class AttendanceStatus(str, enum.Enum):
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    FLAGGED = "FLAGGED"
    REJECTED = "REJECTED"


class Attendance(Base, UUIDMixin, TimestampMixin):
    """Daily attendance record for a user, including GPS and selfie data."""

    __tablename__ = "attendance"
    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_attendance_user_date"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    punch_in_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    punch_out_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    punch_in_gps_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    punch_in_gps_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    punch_out_gps_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    punch_out_gps_lng: Mapped[float | None] = mapped_column(Float, nullable=True)

    selfie_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    liveness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    flag_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    ticket_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tickets.id", ondelete="SET NULL"), nullable=True
    )

    status: Mapped[AttendanceStatus] = mapped_column(
        Enum(AttendanceStatus, name="attendance_status_enum"),
        default=AttendanceStatus.PENDING_APPROVAL,
        nullable=False,
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approval_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    user: Mapped["User | None"] = relationship(
        "User",
        back_populates="attendance_records",
        foreign_keys=[user_id],
        lazy="select",
    )
    approver: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[approved_by],
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<Attendance user={self.user_id} date={self.date} status={self.status}>"
