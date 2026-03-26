from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.attendance import Attendance, AttendanceStatus
from app.repositories.base import BaseRepository


class AttendanceRepository(BaseRepository[Attendance]):
    model = Attendance

    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def get_today_record(self, user_id: UUID, today: date) -> Attendance | None:
        """Return today's attendance record for a user, if any."""
        return (
            self.db.query(Attendance)
            .filter(Attendance.user_id == user_id, Attendance.date == today)
            .first()
        )

    def list_pending(
        self,
        skip: int = 0,
        limit: int = 100,
        exclude_user_id: UUID | None = None,
    ) -> list[Attendance]:
        """Return all records awaiting approval.

        Args:
            exclude_user_id: When provided, the attendance record belonging
                to this user is excluded from the results.  Used so that a
                moderator never sees (or can approve) their own record.
        """
        q = self.db.query(Attendance).filter(
            Attendance.status == AttendanceStatus.PENDING_APPROVAL
        )
        if exclude_user_id is not None:
            q = q.filter(Attendance.user_id != exclude_user_id)
        return q.offset(skip).limit(limit).all()

    def list_for_user(
        self, user_id: UUID, from_date: date | None, to_date: date | None, skip: int, limit: int
    ) -> list[Attendance]:
        q = self.db.query(Attendance).filter(Attendance.user_id == user_id)
        if from_date:
            q = q.filter(Attendance.date >= from_date)
        if to_date:
            q = q.filter(Attendance.date <= to_date)
        return q.order_by(Attendance.date.desc()).offset(skip).limit(limit).all()

    def list_all_range(
        self, from_date: date | None, to_date: date | None, skip: int, limit: int
    ) -> list[Attendance]:
        q = self.db.query(Attendance)
        if from_date:
            q = q.filter(Attendance.date >= from_date)
        if to_date:
            q = q.filter(Attendance.date <= to_date)
        return q.order_by(Attendance.date.desc()).offset(skip).limit(limit).all()

    def list_for_month(self, year: int, month: int) -> list[Attendance]:
        """Return all attendance records for a given calendar month, ordered by date then user."""
        from calendar import monthrange
        from sqlalchemy.orm import joinedload

        first_day = date(year, month, 1)
        last_day = date(year, month, monthrange(year, month)[1])
        return (
            self.db.query(Attendance)
            .options(joinedload(Attendance.user))
            .filter(Attendance.date >= first_day, Attendance.date <= last_day)
            .order_by(Attendance.date, Attendance.user_id)
            .all()
        )

    def count_pending(self) -> int:
        return (
            self.db.query(Attendance)
            .filter(Attendance.status == AttendanceStatus.PENDING_APPROVAL)
            .count()
        )

    def list_for_user_full(
        self,
        user_id: UUID,
        skip: int = 0,
        limit: int = 200,
    ) -> list[Attendance]:
        """
        Return attendance records for a user with both user and approver
        relationships loaded — used for the owner's per-staff detail view.
        """
        from sqlalchemy.orm import joinedload, aliased
        from app.models.user import User

        return (
            self.db.query(Attendance)
            .options(
                joinedload(Attendance.user),
                joinedload(Attendance.approver),
            )
            .filter(Attendance.user_id == user_id)
            .order_by(Attendance.date.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def list_all_with_approver(
        self,
        from_date: date | None,
        to_date: date | None,
        skip: int,
        limit: int,
    ) -> list[Attendance]:
        """
        Return all attendance records with user + approver relationships loaded,
        optionally filtered by date range.
        """
        from sqlalchemy.orm import joinedload

        q = (
            self.db.query(Attendance)
            .options(
                joinedload(Attendance.user),
                joinedload(Attendance.approver),
            )
        )
        if from_date:
            q = q.filter(Attendance.date >= from_date)
        if to_date:
            q = q.filter(Attendance.date <= to_date)
        return q.order_by(Attendance.date.desc()).offset(skip).limit(limit).all()
