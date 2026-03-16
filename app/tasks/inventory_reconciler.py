from __future__ import annotations

import logging

from sqlalchemy.orm import Session

logger = logging.getLogger("opsly.inventory_reconciler")


def check_overdue_checkouts(db: Session) -> None:
    """
    Nightly inventory reconciliation (runs at 02:00 IST via APScheduler).

    Finds all serialized inventory items that have been CHECKED_OUT for more
    than 48 hours and notifies the owner.
    """
    from app.repositories.inventory_repo import InventoryRepository
    from app.services.notification_service import NotificationService

    repo = InventoryRepository(db)
    overdue_items = repo.list_overdue_checkouts(hours=48)

    if overdue_items:
        logger.warning(
            "Found %d overdue checked-out items (>48h)", len(overdue_items)
        )
        NotificationService(db).notify_overdue_parts(overdue_items)
    else:
        logger.info("No overdue inventory items found.")
