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

    def list_pending(self, skip: int = 0, limit: int = 100) -> list[Attendance]:
        """Return all records awaiting approval."""
        return (
            self.db.query(Attendance)
            .filter(Attendance.status == AttendanceStatus.PENDING_APPROVAL)
            .offset(skip)
            .limit(limit)
            .all()
        )

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

    def count_pending(self) -> int:
        return (
            self.db.query(Attendance)
            .filter(Attendance.status == AttendanceStatus.PENDING_APPROVAL)
            .count()
        )
