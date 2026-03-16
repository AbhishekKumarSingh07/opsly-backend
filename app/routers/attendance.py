from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db, require_role
from app.repositories.attendance_repo import AttendanceRepository
from app.schemas.attendance import (
    AttendanceApproveSchema,
    AttendanceFlagSchema,
    AttendancePunchInSchema,
    AttendancePunchOutSchema,
    AttendanceResponse,
)
from app.services.attendance_service import AttendanceService

router = APIRouter(prefix="/attendance", tags=["Attendance"])


@router.post("/punch-in", response_model=AttendanceResponse)
def punch_in(
    payload: AttendancePunchInSchema,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Record a punch-in for the authenticated user.

    - GPS coordinates are validated using the Haversine formula.
    - Out-of-range or low liveness → record is FLAGGED (not rejected).
    - Accessible by: staff, moderator, owner.
    """
    service = AttendanceService(db)
    return service.punch_in(current_user, payload)


@router.post("/punch-out", response_model=AttendanceResponse)
def punch_out(
    payload: AttendancePunchOutSchema,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Record a punch-out for the authenticated user.

    - Accessible by: staff, moderator, owner.
    """
    service = AttendanceService(db)
    return service.punch_out(current_user, payload)


@router.get("/pending", response_model=list[AttendanceResponse], dependencies=[Depends(require_role("owner", "moderator"))])
def pending_approvals(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """
    Return all attendance records awaiting approval.

    - Accessible by: owner, moderator.
    """
    repo = AttendanceRepository(db)
    return repo.list_pending(skip=skip, limit=limit)


@router.patch("/{attendance_id}/approve", response_model=AttendanceResponse)
def approve_attendance(
    attendance_id: UUID,
    payload: AttendanceApproveSchema,
    current_user=Depends(require_role("owner", "moderator")),
    db: Session = Depends(get_db),
):
    """
    Approve an attendance record.

    - Cannot self-approve.
    - Accessible by: owner, moderator.
    """
    service = AttendanceService(db)
    return service.approve_attendance(attendance_id, current_user, payload.notes)


@router.patch("/{attendance_id}/flag", response_model=AttendanceResponse)
def flag_attendance(
    attendance_id: UUID,
    payload: AttendanceFlagSchema,
    current_user=Depends(require_role("owner", "moderator")),
    db: Session = Depends(get_db),
):
    """
    Flag an attendance record with a reason.

    - Only Owner can reverse an already-approved record.
    - Accessible by: owner, moderator.
    """
    service = AttendanceService(db)
    return service.flag_attendance(attendance_id, current_user, payload.reason)


@router.get("/my", response_model=list[AttendanceResponse])
def my_attendance(
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    skip: int = 0,
    limit: int = 50,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return own attendance records, optionally filtered by date range.

    - Accessible by: all roles.
    """
    repo = AttendanceRepository(db)
    return repo.list_for_user(current_user.id, from_date, to_date, skip, limit)


@router.get("/", response_model=list[AttendanceResponse], dependencies=[Depends(require_role("owner"))])
def all_attendance(
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """
    Return all staff attendance records with optional date range filter.

    - Accessible by: owner only.
    """
    repo = AttendanceRepository(db)
    return repo.list_all_range(from_date, to_date, skip, limit)
