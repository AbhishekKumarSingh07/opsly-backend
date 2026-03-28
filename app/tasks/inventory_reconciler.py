from __future__ import annotations

import logging

from sqlalchemy.orm import Session

logger = logging.getLogger("opsly.inventory_reconciler")


def check_low_stock(db: Session) -> None:
    """
    Nightly inventory low-stock check (runs at 02:00 IST via APScheduler).

    Finds all inventory items whose quantity is at or below their effective
    low-stock threshold and notifies the owner.
    """
    from app.repositories.inventory_repo import InventoryRepository
    from app.services.notification_service import NotificationService

    repo = InventoryRepository(db)
    low_stock_items = repo.list_low_stock()

    if low_stock_items:
        logger.warning(
            "Found %d low-stock inventory items", len(low_stock_items)
        )
        NotificationService(db).notify_low_stock(low_stock_items)
    else:
        logger.info("No low-stock inventory items found.")
