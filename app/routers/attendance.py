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
    AttendanceAdminAddSchema,
    AttendancePunchInSchema,
    AttendancePunchOutSchema,
    AttendanceResponse,
    AttendanceCalendarDay,
    AttendanceCalendarEntry,
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
    record = service.punch_in(current_user, payload)
    return AttendanceResponse.from_orm_with_user(record)


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
    record = service.punch_out(current_user, payload)
    return AttendanceResponse.from_orm_with_user(record)


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
    records = repo.list_pending(skip=skip, limit=limit)
    return [AttendanceResponse.from_orm_with_user(r) for r in records]


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
    record = service.approve_attendance(attendance_id, current_user, payload.notes)
    return AttendanceResponse.from_orm_with_user(record)


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
    record = service.flag_attendance(attendance_id, current_user, payload.reason)
    return AttendanceResponse.from_orm_with_user(record)


@router.post("/admin-add", response_model=AttendanceResponse)
def admin_add_attendance(
    payload: AttendanceAdminAddSchema,
    current_user=Depends(require_role("owner", "moderator")),
    db: Session = Depends(get_db),
):
    """
    Directly create an approved attendance record for a staff member.

    - No punch-in request is needed from the staff member.
    - The record is immediately set to APPROVED; the caller's ID is recorded as approver.
    - Moderators can only add records for staff users.
    - Owner can add records for any user.
    - Raises 409 if a record already exists for the user on that date.
    - Accessible by: owner, moderator.
    """
    service = AttendanceService(db)
    record = service.admin_add_attendance(current_user, payload)
    return AttendanceResponse.from_orm_with_user(record)


@router.get("/calendar", response_model=list[AttendanceCalendarDay], dependencies=[Depends(require_role("owner", "moderator"))])
def attendance_calendar(
    year: int = Query(..., ge=2020, le=2099, description="Calendar year, e.g. 2026"),
    month: int = Query(..., ge=1, le=12, description="Calendar month 1–12"),
    db: Session = Depends(get_db),
):
    """
    Return all attendance records for a given month, grouped by date.

    Each day lists every user who has a record on that date with their
    name and attendance status — used to render the owner's calendar view.

    Accessible by: owner, moderator.
    """
    from collections import defaultdict

    repo = AttendanceRepository(db)
    records = repo.list_for_month(year, month)

    # Group by date
    by_date: dict[date, list[AttendanceCalendarEntry]] = defaultdict(list)
    for rec in records:
        user = getattr(rec, "user", None)
        user_name = getattr(user, "name", None) or "Unknown"
        by_date[rec.date].append(
            AttendanceCalendarEntry(
                attendance_id=rec.id,
                user_id=rec.user_id,
                user_name=user_name,
                status=rec.status,
                punch_in_time=rec.punch_in_time,
                punch_out_time=rec.punch_out_time,
            )
        )

    return [
        AttendanceCalendarDay(date=d, entries=entries)
        for d, entries in sorted(by_date.items())
    ]


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
    records = repo.list_for_user(current_user.id, from_date, to_date, skip, limit)
    return [AttendanceResponse.from_orm_with_user(r) for r in records]


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
    records = repo.list_all_range(from_date, to_date, skip, limit)
    return [AttendanceResponse.from_orm_with_user(r) for r in records]
