from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError, PermissionDeniedError
from app.core.permissions import PermissionPolicy
from app.models.attendance import Attendance, AttendanceStatus
from app.models.user import User, UserRole
from app.repositories.attendance_repo import AttendanceRepository
from app.repositories.ticket_repo import TicketRepository
from app.schemas.attendance import AttendancePunchInSchema, AttendancePunchOutSchema
from app.utils.geo import is_within_radius

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
        - GPS is validated using Haversine formula.
          Staff → validated against ticket site GPS (ticket_id required).
          Moderator/Owner → validated against office GPS from settings.
        - If outside radius: record is FLAGGED (not rejected).
        - Liveness score < 0.7 → FLAGGED.
        """
        from datetime import date

        today = datetime.now(timezone.utc).date()
        existing = self.repo.get_today_record(user.id, today)
        if existing:
            raise ConflictError("Attendance record already exists for today.")

        # GPS geofence validation
        flag_reason: str | None = None
        status = AttendanceStatus.PENDING_APPROVAL

        if user.role == UserRole.staff:
            if not payload.ticket_id:
                raise BusinessRuleError(
                    "TICKET_REQUIRED",
                    "staff must provide ticket_id for punch-in GPS validation.",
                )
            ticket_repo = TicketRepository(self.db)
            ticket = ticket_repo.get_by_id(payload.ticket_id)
            if not ticket:
                raise NotFoundError("Ticket", str(payload.ticket_id))

            dg_set = ticket.dg_set
            site = dg_set.site if dg_set else None
            if site and site.gps_lat is not None and site.gps_lng is not None:
                in_range = is_within_radius(
                    payload.gps_lat, payload.gps_lng,
                    site.gps_lat, site.gps_lng,
                    settings.GEOFENCE_RADIUS_METERS,
                )
                if not in_range:
                    flag_reason = "GPS_OUT_OF_RANGE"
                    status = AttendanceStatus.FLAGGED
                    logger.info("Punch-in flagged GPS_OUT_OF_RANGE for user %s", user.id)
        else:
            # Moderator / Owner → office geofence
            in_range = is_within_radius(
                payload.gps_lat, payload.gps_lng,
                settings.OFFICE_GPS_LAT, settings.OFFICE_GPS_LNG,
                settings.GEOFENCE_RADIUS_METERS,
            )
            if not in_range:
                flag_reason = "GPS_OUT_OF_RANGE"
                status = AttendanceStatus.FLAGGED
                logger.info("Punch-in flagged GPS_OUT_OF_RANGE for user %s", user.id)

        # Liveness check
        if payload.liveness_score < 0.7:
            if flag_reason:
                flag_reason = f"{flag_reason},LIVENESS_CHECK_FAILED"
            else:
                flag_reason = "LIVENESS_CHECK_FAILED"
            status = AttendanceStatus.FLAGGED

        attendance = Attendance(
            user_id=user.id,
            date=today,
            punch_in_time=datetime.now(timezone.utc),
            punch_in_gps_lat=payload.gps_lat,
            punch_in_gps_lng=payload.gps_lng,
            selfie_url=payload.selfie_url,
            liveness_score=payload.liveness_score,
            ticket_id=payload.ticket_id,
            status=status,
            flag_reason=flag_reason,
        )

        result = self.repo.create(attendance)

        if status == AttendanceStatus.FLAGGED:
            self._notify_moderators_flagged(user, flag_reason or "")

        return result

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

    def _notify_moderators_flagged(self, user: User, reason: str) -> None:
        """Stub: notify moderators of a flagged punch-in."""
        from app.services.notification_service import NotificationService
        NotificationService(self.db).notify_flagged_attendance(user, reason)
