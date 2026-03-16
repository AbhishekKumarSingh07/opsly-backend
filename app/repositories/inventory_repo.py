from __future__ import annotations

from datetime import datetime, timezone, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.inventory import InventoryItem, InventoryItemStatus, InventoryMovement, InventoryStock
from app.repositories.base import BaseRepository


class InventoryRepository(BaseRepository[InventoryItem]):
    model = InventoryItem

    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def get_by_barcode(self, barcode: str) -> InventoryItem | None:
        return (
            self.db.query(InventoryItem)
            .filter(InventoryItem.barcode == barcode, InventoryItem.is_deleted.is_(False))
            .first()
        )

    def get_by_serial(self, serial_no: str) -> InventoryItem | None:
        return (
            self.db.query(InventoryItem)
            .filter(InventoryItem.serial_no == serial_no, InventoryItem.is_deleted.is_(False))
            .first()
        )

    def list_checked_out_for_ticket(self, ticket_id: UUID) -> list[InventoryItem]:
        return (
            self.db.query(InventoryItem)
            .filter(
                InventoryItem.current_ticket_id == ticket_id,
                InventoryItem.status == InventoryItemStatus.CHECKED_OUT,
                InventoryItem.is_deleted.is_(False),
            )
            .all()
        )

    def list_overdue_checkouts(self, hours: int = 48) -> list[InventoryItem]:
        """Return items checked out for more than `hours` hours."""
        threshold = datetime.now(timezone.utc) - timedelta(hours=hours)
        return (
            self.db.query(InventoryItem)
            .filter(
                InventoryItem.status == InventoryItemStatus.CHECKED_OUT,
                InventoryItem.checked_out_at <= threshold,
                InventoryItem.is_deleted.is_(False),
            )
            .all()
        )

    def count_in_field(self) -> int:
        return (
            self.db.query(InventoryItem)
            .filter(
                InventoryItem.status.in_([
                    InventoryItemStatus.CHECKED_OUT,
                    InventoryItemStatus.PENDING_RETURN,
                ]),
                InventoryItem.is_deleted.is_(False),
            )
            .count()
        )

    def add_movement(self, movement: InventoryMovement) -> InventoryMovement:
        self.db.add(movement)
        self.db.flush()
        return movement

    def list_low_stock(self, db: Session) -> list[InventoryStock]:
        return (
            db.query(InventoryStock)
            .filter(
                InventoryStock.quantity_in_stock <= InventoryStock.reorder_level,
                InventoryStock.is_deleted.is_(False),
            )
            .all()
        )
