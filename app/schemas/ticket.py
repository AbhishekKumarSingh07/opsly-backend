from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.ticket import PhotoType, TicketPriority, TicketStatus


class TicketCreate(BaseModel):
    """Request body for creating a new ticket."""

    model_config = ConfigDict(from_attributes=True)

    dg_set_id: UUID | None = None
    reported_issue: str
    priority: TicketPriority = TicketPriority.MEDIUM
    notes: str | None = None


class TicketAssign(BaseModel):
    """Request body for assigning technicians to a ticket."""

    model_config = ConfigDict(from_attributes=True)

    technician_ids: list[UUID]


class TicketStatusUpdate(BaseModel):
    """Request body for status transitions."""

    model_config = ConfigDict(from_attributes=True)

    new_status: TicketStatus
    notes: str | None = None


class TicketPhotoCreate(BaseModel):
    """Metadata for a ticket photo upload."""

    model_config = ConfigDict(from_attributes=True)

    photo_type: PhotoType
    s3_url: str
    gps_lat: float | None = None
    gps_lng: float | None = None

    @field_validator("gps_lat")
    @classmethod
    def validate_lat(cls, v: float | None) -> float | None:
        if v is not None and not (-90 <= v <= 90):
            raise ValueError("Latitude must be between -90 and 90")
        return v

    @field_validator("gps_lng")
    @classmethod
    def validate_lng(cls, v: float | None) -> float | None:
        if v is not None and not (-180 <= v <= 180):
            raise ValueError("Longitude must be between -180 and 180")
        return v


class TicketPhotoResponse(BaseModel):
    """Photo attachment response model."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ticket_id: UUID
    photo_type: PhotoType
    s3_url: str
    gps_lat: float | None
    gps_lng: float | None
    uploaded_by: UUID
    uploaded_at: datetime


class TicketResponse(BaseModel):
    """Full ticket response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    reference_no: str
    dg_set_id: UUID | None
    created_by: UUID
    status: TicketStatus
    priority: TicketPriority
    reported_issue: str
    notes: str | None
    completed_at: datetime | None
    invoiced_at: datetime | None
    created_at: datetime
    updated_at: datetime | None
    photos: list[TicketPhotoResponse] = []
