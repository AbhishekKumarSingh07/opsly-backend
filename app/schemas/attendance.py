from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.attendance import AttendanceStatus


class AttendancePunchInSchema(BaseModel):
    """Request body for punching in.

    GPS coordinates are captured silently on the client side and sent
    with the request. No selfie or liveness check is required — the
    attendance record is always created as PENDING_APPROVAL and is
    subject to moderator/owner review.
    """

    model_config = ConfigDict(from_attributes=True)

    gps_lat: float
    gps_lng: float
    ticket_id: UUID | None = None  # Required for staff; optional for others

    @field_validator("gps_lat")
    @classmethod
    def validate_lat(cls, v: float) -> float:
        if not (-90 <= v <= 90):
            raise ValueError("Latitude must be between -90 and 90")
        return v

    @field_validator("gps_lng")
    @classmethod
    def validate_lng(cls, v: float) -> float:
        if not (-180 <= v <= 180):
            raise ValueError("Longitude must be between -180 and 180")
        return v


class AttendancePunchOutSchema(BaseModel):
    """Request body for punching out."""

    model_config = ConfigDict(from_attributes=True)

    gps_lat: float
    gps_lng: float

    @field_validator("gps_lat")
    @classmethod
    def validate_lat(cls, v: float) -> float:
        if not (-90 <= v <= 90):
            raise ValueError("Latitude must be between -90 and 90")
        return v

    @field_validator("gps_lng")
    @classmethod
    def validate_lng(cls, v: float) -> float:
        if not (-180 <= v <= 180):
            raise ValueError("Longitude must be between -180 and 180")
        return v


class AttendanceApproveSchema(BaseModel):
    """Request body for approving or flagging attendance."""

    model_config = ConfigDict(from_attributes=True)

    notes: str | None = None


class AttendanceFlagSchema(BaseModel):
    """Request body for flagging an attendance record."""

    model_config = ConfigDict(from_attributes=True)

    reason: str


class AttendanceAdminAddSchema(BaseModel):
    """
    Request body for moderator/owner to directly add an attendance record
    for a staff member without a punch-in request.

    The record is immediately set to APPROVED with the caller as approver.
    """

    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    date: date
    punch_in_time: datetime
    punch_out_time: datetime | None = None
    gps_lat: float | None = None
    gps_lng: float | None = None
    ticket_id: UUID | None = None
    notes: str | None = None


class AttendanceCalendarEntry(BaseModel):
    """A single user's attendance record summarised for the calendar view."""

    model_config = ConfigDict(from_attributes=True)

    attendance_id: UUID
    user_id: UUID
    user_name: str
    status: AttendanceStatus
    punch_in_time: datetime
    punch_out_time: datetime | None = None


class AttendanceCalendarDay(BaseModel):
    """All attendance entries for one calendar date."""

    date: date
    entries: list[AttendanceCalendarEntry]


class AttendanceResponse(BaseModel):
    """Attendance record response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    user_name: str | None = None  # Populated from user relationship
    date: date
    punch_in_time: datetime
    punch_out_time: datetime | None
    punch_in_gps_lat: float | None
    punch_in_gps_lng: float | None
    punch_out_gps_lat: float | None
    punch_out_gps_lng: float | None
    flag_reason: str | None
    status: AttendanceStatus
    approved_by: UUID | None
    approved_by_name: str | None = None  # Approver's display name
    approved_at: datetime | None
    approval_notes: str | None
    ticket_id: UUID | None
    created_at: datetime

    @classmethod
    def from_orm_with_user(cls, record: object) -> "AttendanceResponse":
        """Build response, resolving user name and approver name from relationships."""
        obj = cls.model_validate(record)
        user = getattr(record, "user", None)
        if user is not None:
            obj.user_name = getattr(user, "full_name", None) or getattr(user, "name", None)
        approver = getattr(record, "approver", None)
        if approver is not None:
            obj.approved_by_name = getattr(approver, "name", None)
        return obj


# ─── Staff Attendance Summary (Owner view) ────────────────────────────────────

class StaffMonthlyAttendanceSummary(BaseModel):
    """
    Monthly attendance summary for a single staff/moderator member.
    Used by the owner's staff management page.
    """

    user_id: UUID
    user_name: str
    user_role: str
    year: int
    month: int              # 1–12
    total_working_days: int  # Calendar working days in the month (Mon–Sat)
    present_days: int        # Records with status APPROVED
    pending_days: int        # Records with status PENDING_APPROVAL
    flagged_days: int        # Records with status FLAGGED
    absent_days: int         # total_working_days - present_days
    attendance_pct: float    # present_days / total_working_days × 100


class StaffOverallAttendanceSummary(BaseModel):
    """
    Overall (all-time) attendance snapshot for a single staff/moderator.
    Includes a breakdown per month and approver info for each record.
    """

    user_id: UUID
    user_name: str
    user_role: str
    total_approved: int
    total_pending: int
    total_flagged: int
    monthly_breakdown: list[StaffMonthlyAttendanceSummary]
    recent_records: list[AttendanceResponse]   # last 30 records, newest first
