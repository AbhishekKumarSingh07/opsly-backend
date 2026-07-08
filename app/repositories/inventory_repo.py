from __future__ import annotations

from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.inventory import (
    InventoryCategory,
    InventoryDispatch,
    InventoryItem,
)
from app.repositories.base import BaseRepository


class CategoryRepository(BaseRepository[InventoryCategory]):
    model = InventoryCategory

    def get_by_name(self, name: str) -> InventoryCategory | None:
        return (
            self.db.query(InventoryCategory)
            .filter(InventoryCategory.category_name == name, InventoryCategory.is_deleted.is_(False))
            .first()
        )

    def item_count(self, category_id: UUID) -> int:
        return (
            self.db.query(InventoryItem)
            .filter(
                InventoryItem.category_id == category_id,
                InventoryItem.is_deleted.is_(False),
            )
            .count()
        )

    def list_all_with_counts(self) -> list[tuple[InventoryCategory, int]]:
        rows = (
            self.db.query(InventoryCategory, func.count(InventoryItem.id).label("cnt"))
            .outerjoin(
                InventoryItem,
                (InventoryItem.category_id == InventoryCategory.id) & (InventoryItem.is_deleted.is_(False)),
            )
            .filter(InventoryCategory.is_deleted.is_(False))
            .group_by(InventoryCategory.id)
            .order_by(InventoryCategory.category_name)
            .all()
        )
        return [(cat, cnt) for cat, cnt in rows]


class InventoryRepository(BaseRepository[InventoryItem]):
    model = InventoryItem

    def get_by_part_number(self, part_number: str) -> InventoryItem | None:
        if not part_number:
            return None
        return (
            self.db.query(InventoryItem)
            .filter(InventoryItem.part_number == part_number, InventoryItem.is_deleted.is_(False))
            .first()
        )

    def get_by_barcode(self, barcode: str) -> InventoryItem | None:
        return (
            self.db.query(InventoryItem)
            .filter(InventoryItem.barcode == barcode, InventoryItem.is_deleted.is_(False))
            .first()
        )

    def list_filtered(
        self,
        skip: int = 0,
        limit: int = 20,
        category_id: UUID | None = None,
        search: str | None = None,
        low_stock_only: bool = False,
    ) -> list[InventoryItem]:
        q = self.db.query(InventoryItem).filter(InventoryItem.is_deleted.is_(False))
        if category_id:
            q = q.filter(InventoryItem.category_id == category_id)
        if search:
            pattern = f"%{search}%"
            q = q.filter(
                InventoryItem.part_name.ilike(pattern)
                | InventoryItem.part_number.ilike(pattern)
                | InventoryItem.barcode.ilike(pattern)
            )
        if low_stock_only:
            q = q.filter(InventoryItem.quantity <= InventoryItem.low_stock_threshold)
        return q.order_by(InventoryItem.part_name).offset(skip).limit(limit).all()

    def count_filtered(
        self,
        category_id: UUID | None = None,
        search: str | None = None,
        low_stock_only: bool = False,
    ) -> int:
        q = self.db.query(InventoryItem).filter(InventoryItem.is_deleted.is_(False))
        if category_id:
            q = q.filter(InventoryItem.category_id == category_id)
        if search:
            pattern = f"%{search}%"
            q = q.filter(
                InventoryItem.part_name.ilike(pattern)
                | InventoryItem.part_number.ilike(pattern)
                | InventoryItem.barcode.ilike(pattern)
            )
        if low_stock_only:
            q = q.filter(InventoryItem.quantity <= InventoryItem.low_stock_threshold)
        return q.count()

    def list_low_stock(self) -> list[InventoryItem]:
        return (
            self.db.query(InventoryItem)
            .filter(
                InventoryItem.is_deleted.is_(False),
                InventoryItem.quantity <= InventoryItem.low_stock_threshold,
            )
            .order_by(InventoryItem.quantity)
            .all()
        )


class InventoryDispatchRepository(BaseRepository[InventoryDispatch]):
    model = InventoryDispatch

    def list_by_item(
        self, item_id: UUID, skip: int = 0, limit: int = 50
    ) -> list[InventoryDispatch]:
        return (
            self.db.query(InventoryDispatch)
            .filter(InventoryDispatch.inventory_item_id == item_id)
            .order_by(InventoryDispatch.dispatched_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def list_by_ticket(self, ticket_id: UUID) -> list[InventoryDispatch]:
        return (
            self.db.query(InventoryDispatch)
            .filter(InventoryDispatch.ticket_id == ticket_id)
            .order_by(InventoryDispatch.dispatched_at.desc())
            .all()
        )

    def list_by_category(
        self, category_id: UUID, skip: int = 0, limit: int = 50
    ) -> list[InventoryDispatch]:
        return (
            self.db.query(InventoryDispatch)
            .join(InventoryItem, InventoryDispatch.inventory_item_id == InventoryItem.id)
            .filter(InventoryItem.category_id == category_id)
            .order_by(InventoryDispatch.dispatched_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

