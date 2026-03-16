from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.attendance import AttendanceStatus


class AttendancePunchInSchema(BaseModel):
    """Request body for punching in."""

    model_config = ConfigDict(from_attributes=True)

    gps_lat: float
    gps_lng: float
    selfie_url: str
    liveness_score: float
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

    @field_validator("liveness_score")
    @classmethod
    def validate_liveness(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("liveness_score must be between 0.0 and 1.0")
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


class AttendanceResponse(BaseModel):
    """Attendance record response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    date: date
    punch_in_time: datetime
    punch_out_time: datetime | None
    punch_in_gps_lat: float | None
    punch_in_gps_lng: float | None
    punch_out_gps_lat: float | None
    punch_out_gps_lng: float | None
    selfie_url: str | None
    liveness_score: float | None
    flag_reason: str | None
    status: AttendanceStatus
    approved_by: UUID | None
    approved_at: datetime | None
    approval_notes: str | None
    ticket_id: UUID | None
    created_at: datetime
