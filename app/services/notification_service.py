from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.models.user import User, UserRole

logger = logging.getLogger("opsly.notifications")


class NotificationService:
    """
    Stub notification service.
    In production, replace log calls with actual push/email/SMS dispatch.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def notify_flagged_attendance(self, user: User, reason: str) -> None:
        """Notify moderators when a punch-in is flagged."""
        from app.repositories.user_repo import UserRepository
        moderators = UserRepository(self.db).list_by_role(UserRole.moderator.value)
        for mod in moderators:
            logger.info(
                "[NOTIFY] Moderator %s: Flagged attendance for user %s — reason: %s",
                mod.email, user.email, reason,
            )

    def notify_amc_due(self, dg_set_id: str, days_until_due: int) -> None:
        """Notify moderators of upcoming AMC service."""
        logger.info(
            "[NOTIFY] AMC due in %d days for DG set %s", days_until_due, dg_set_id
        )

    def notify_overdue_parts(self, items: list) -> None:
        """Notify owner of parts that have been checked out > 48 hours."""
        logger.info(
            "[NOTIFY] %d parts overdue return: %s",
            len(items), [str(getattr(i, "id", "?")) for i in items],
        )

    def notify_parts_dispatched(self, ticket_id: str) -> None:
        """Notify technician that parts have been dispatched for their ticket."""
        logger.info("[NOTIFY] Parts dispatched for ticket %s", ticket_id)

    def notify_escalation(self, dg_set_id: str, message: str) -> None:
        """Send escalation notification to owner."""
        logger.warning("[ESCALATION] DG set %s: %s", dg_set_id, message)
