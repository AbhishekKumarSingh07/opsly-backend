from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError, PermissionDeniedError
from app.core.permissions import PermissionPolicy
from app.models.attendance import Attendance, AttendanceStatus
from app.models.user import User, UserRole
from app.repositories.attendance_repo import AttendanceRepository
from app.repositories.ticket_repo import TicketRepository
from app.schemas.attendance import AttendancePunchInSchema, AttendancePunchOutSchema, AttendanceAdminAddSchema

logger = logging.getLogger("opsly.attendance")


class AttendanceService:
    """Business logic for attendance punch-in, punch-out, approval and flagging."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = AttendanceRepository(db)

    def punch_in(self, user: User, payload: AttendancePunchInSchema) -> Attendance:
        """
        Record a punch-in event for the given user.

        Rules:
        - One punch-in per user per calendar day.
        - GPS coordinates are recorded silently in the background; no
          geofence error is raised and no flag is set automatically.
        - The record is always created as PENDING_APPROVAL and must be
          approved (or flagged) by a moderator or owner.
        - ticket_id is optional for all roles; GPS location alone is
          sufficient. ticket_id can be linked later during approval.
        """
        from datetime import date

        today = datetime.now(timezone.utc).date()
        existing = self.repo.get_today_record(user.id, today)
        if existing:
            raise ConflictError("Attendance record already exists for today.")

        # If a ticket_id is provided by any role, validate it exists.
        # ticket_id is optional — GPS coordinates are sufficient for
        # attendance submission; association with a ticket can be done
        # later by a moderator/owner during approval.
        if payload.ticket_id:
            ticket_repo = TicketRepository(self.db)
            ticket = ticket_repo.get_by_id(payload.ticket_id)
            if not ticket:
                raise NotFoundError("Ticket", str(payload.ticket_id))

        attendance = Attendance(
            user_id=user.id,
            date=today,
            punch_in_time=datetime.now(timezone.utc),
            punch_in_gps_lat=payload.gps_lat,
            punch_in_gps_lng=payload.gps_lng,
            ticket_id=payload.ticket_id,
            status=AttendanceStatus.PENDING_APPROVAL,
        )

        logger.info(
            "Punch-in created for user %s at (%.5f, %.5f) — awaiting approval",
            user.id, payload.gps_lat, payload.gps_lng,
        )
        return self.repo.create(attendance)

    def punch_out(self, user: User, payload: AttendancePunchOutSchema) -> Attendance:
        """Record punch-out time and GPS for today's open attendance record."""
        from datetime import date

        today = datetime.now(timezone.utc).date()
        record = self.repo.get_today_record(user.id, today)
        if not record:
            raise NotFoundError("Attendance record for today")
        if record.punch_out_time:
            raise ConflictError("Already punched out today.")

        record.punch_out_time = datetime.now(timezone.utc)
        record.punch_out_gps_lat = payload.gps_lat
        record.punch_out_gps_lng = payload.gps_lng
        return self.repo.save(record)

    def approve_attendance(self, attendance_id: UUID, approver: User, notes: str | None) -> Attendance:
        """
        Approve a pending attendance record.

        Hierarchy enforced via PermissionPolicy:
        - Owner can approve anyone.
        - Moderator can only approve staff attendance.
        - Nobody can self-approve.
        """
        record = self.repo.get_by_id(attendance_id)
        if not record:
            raise NotFoundError("Attendance", str(attendance_id))

        if record.status == AttendanceStatus.APPROVED:
            raise BusinessRuleError("ALREADY_APPROVED", "Attendance record is already approved.")

        # Load the target user so we can check their role
        from app.repositories.user_repo import UserRepository
        target_user = UserRepository(self.db).get_by_id(record.user_id)
        if not target_user:
            raise NotFoundError("User", str(record.user_id))

        PermissionPolicy(approver).require_can_approve_attendance(target_user)

        record.status = AttendanceStatus.APPROVED
        record.approved_by = approver.id
        record.approved_at = datetime.now(timezone.utc)
        record.approval_notes = notes
        return self.repo.save(record)

    def flag_attendance(self, attendance_id: UUID, flagger: User, reason: str) -> Attendance:
        """
        Flag an attendance record. Only Owner can reverse a previously approved record.
        """
        record = self.repo.get_by_id(attendance_id)
        if not record:
            raise NotFoundError("Attendance", str(attendance_id))

        if record.status == AttendanceStatus.APPROVED and flagger.role != UserRole.owner:
            raise PermissionDeniedError("Only an Owner can reverse an approved attendance record.")

        record.status = AttendanceStatus.FLAGGED
        record.flag_reason = reason
        return self.repo.save(record)

    def admin_add_attendance(
        self,
        approver: User,
        payload: AttendanceAdminAddSchema,
    ) -> Attendance:
        """
        Moderator/Owner directly creates an approved attendance record for a staff member.

        Rules:
        - Moderators can only add records for staff users.
        - Owner can add records for anyone.
        - Duplicate date protection: raises ConflictError if a record already
          exists for that user on that date.
        - The record is immediately APPROVED with the caller as approver.
        """
        from app.repositories.user_repo import UserRepository

        target_user = UserRepository(self.db).get_by_id(payload.user_id)
        if not target_user:
            raise NotFoundError("User", str(payload.user_id))

        # Moderators may only add attendance for staff
        PermissionPolicy(approver).require_can_approve_attendance(target_user)

        existing = self.repo.get_today_record(payload.user_id, payload.date)
        if existing:
            raise ConflictError(
                f"An attendance record for {target_user.name} on {payload.date} already exists."
            )

        attendance = Attendance(
            user_id=payload.user_id,
            date=payload.date,
            punch_in_time=payload.punch_in_time,
            punch_out_time=payload.punch_out_time,
            punch_in_gps_lat=payload.gps_lat,
            punch_in_gps_lng=payload.gps_lng,
            ticket_id=payload.ticket_id,
            status=AttendanceStatus.APPROVED,
            approved_by=approver.id,
            approved_at=datetime.now(timezone.utc),
            approval_notes=payload.notes,
        )

        logger.info(
            "Admin-added attendance for user %s on %s by %s",
            payload.user_id, payload.date, approver.id,
        )
        return self.repo.create(attendance)
