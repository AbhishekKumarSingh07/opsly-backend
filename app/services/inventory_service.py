from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.models.inventory import (
    InventoryCategory,
    InventoryDispatch,
    InventoryItem,
)
from app.models.user import User
from app.repositories.inventory_repo import (
    CategoryRepository,
    InventoryDispatchRepository,
    InventoryRepository,
)
from app.schemas.inventory import (
    BulkImportRow,
    CategoryCreate,
    CategoryUpdate,
    InventoryDispatchCreate,
    InventoryDispatchReturn,
    InventoryItemCreate,
    InventoryItemUpdate,
)


class InventoryService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.cat_repo = CategoryRepository(db)
        self.inv_repo = InventoryRepository(db)
        self.dispatch_repo = InventoryDispatchRepository(db)

    # ── Categories ──────────────────────────────────────────────────────────

    def create_category(self, payload: CategoryCreate, actor: User) -> InventoryCategory:
        if self.cat_repo.get_by_name(payload.category_name):
            raise ConflictError(f"Category '{payload.category_name}' already exists.")
        cat = InventoryCategory(
            category_name=payload.category_name,
            description=payload.description,
        )
        return self.cat_repo.create(cat)

    def update_category(self, cat_id: UUID, payload: CategoryUpdate, actor: User) -> InventoryCategory:
        cat = self.cat_repo.get_by_id(cat_id)
        if not cat or cat.is_deleted:
            raise NotFoundError("InventoryCategory", str(cat_id))
        if payload.category_name and payload.category_name != cat.category_name:
            if self.cat_repo.get_by_name(payload.category_name):
                raise ConflictError(f"Category '{payload.category_name}' already exists.")
            cat.category_name = payload.category_name
        if payload.description is not None:
            cat.description = payload.description
        return self.cat_repo.save(cat)

    def delete_category(self, cat_id: UUID, actor: User) -> None:
        cat = self.cat_repo.get_by_id(cat_id)
        if not cat or cat.is_deleted:
            raise NotFoundError("InventoryCategory", str(cat_id))
        if self.cat_repo.item_count(cat_id) > 0:
            raise BusinessRuleError(
                "CATEGORY_HAS_ITEMS",
                "Cannot delete category that has inventory items. Reassign items first.",
            )
        cat.is_deleted = True
        self.cat_repo.save(cat)

    # ── Inventory Items ──────────────────────────────────────────────────────

    def create_item(self, payload: InventoryItemCreate, actor: User) -> InventoryItem:
        # Only check part_number uniqueness if provided
        if payload.part_number:
            if self.inv_repo.get_by_part_number(payload.part_number):
                raise ConflictError(f"Part number '{payload.part_number}' already exists.")
        if payload.barcode and self.inv_repo.get_by_barcode(payload.barcode):
            raise ConflictError(f"Barcode '{payload.barcode}' already exists.")
        item = InventoryItem(
            part_name=payload.part_name,
            part_number=payload.part_number or None,
            category_id=payload.category_id,
            barcode=payload.barcode or None,
            unit_cost=payload.unit_cost,
            quantity=payload.quantity,
            low_stock_threshold=payload.low_stock_threshold,
        )
        return self.inv_repo.create(item)

    def update_item(self, item_id: UUID, payload: InventoryItemUpdate, actor: User) -> InventoryItem:
        item = self.inv_repo.get_by_id(item_id)
        if not item or item.is_deleted:
            raise NotFoundError("InventoryItem", str(item_id))
        # part_number uniqueness check (only if changing to a non-None value)
        if payload.part_number is not None and payload.part_number != item.part_number:
            existing = self.inv_repo.get_by_part_number(payload.part_number)
            if existing and existing.id != item_id:
                raise ConflictError(f"Part number '{payload.part_number}' already exists.")
        if payload.barcode and payload.barcode != item.barcode:
            if self.inv_repo.get_by_barcode(payload.barcode):
                raise ConflictError(f"Barcode '{payload.barcode}' already exists.")
        for field in ("part_name", "part_number", "category_id", "barcode",
                      "unit_cost", "quantity", "low_stock_threshold"):
            val = getattr(payload, field, None)
            if val is not None:
                setattr(item, field, val)
        return self.inv_repo.save(item)

    def delete_item(self, item_id: UUID, actor: User) -> None:
        item = self.inv_repo.get_by_id(item_id)
        if not item or item.is_deleted:
            raise NotFoundError("InventoryItem", str(item_id))
        item.is_deleted = True
        self.inv_repo.save(item)

    # ── Dispatch ──────────────────────────────────────────────────────────────

    def dispatch_item(self, payload: InventoryDispatchCreate, actor: User) -> InventoryDispatch:
        item = self.inv_repo.get_by_id(payload.inventory_item_id)
        if not item or item.is_deleted:
            raise NotFoundError("InventoryItem", str(payload.inventory_item_id))
        net_dispatched = payload.quantity
        if item.quantity < net_dispatched:
            raise BusinessRuleError(
                "INSUFFICIENT_STOCK",
                f"Cannot dispatch {net_dispatched} units — only {item.quantity} in stock.",
            )
        # Reduce quantity
        item.quantity -= net_dispatched
        self.inv_repo.save(item)

        dispatch = InventoryDispatch(
            inventory_item_id=payload.inventory_item_id,
            ticket_id=payload.ticket_id,
            quantity=payload.quantity,
            dispatched_by=actor.id,
            dispatched_at=datetime.now(timezone.utc),
            part_number_dispatched=item.part_number,
            barcode_dispatched=item.barcode,
            notes=payload.notes,
            returned_quantity=0,
        )
        return self.dispatch_repo.create(dispatch)

    def return_item(
        self, dispatch_id: UUID, payload: InventoryDispatchReturn, actor: User
    ) -> InventoryDispatch:
        dispatch = self.dispatch_repo.get_by_id(dispatch_id)
        if not dispatch:
            raise NotFoundError("InventoryDispatch", str(dispatch_id))
        max_returnable = dispatch.quantity - dispatch.returned_quantity
        if payload.returned_quantity > max_returnable:
            raise BusinessRuleError(
                "RETURN_EXCEEDS_DISPATCHED",
                f"Cannot return {payload.returned_quantity} — only {max_returnable} eligible for return.",
            )
        # Restore quantity
        item = self.inv_repo.get_by_id(dispatch.inventory_item_id)
        if item and not item.is_deleted:
            item.quantity += payload.returned_quantity
            self.inv_repo.save(item)

        dispatch.returned_quantity += payload.returned_quantity
        dispatch.returned_by = actor.id
        dispatch.returned_at = datetime.now(timezone.utc)
        return self.dispatch_repo.save(dispatch)

    # ── Bulk Import ───────────────────────────────────────────────────────────

    def bulk_import_csv(self, csv_content: bytes, actor: User) -> dict:
        text = csv_content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        created = 0
        updated = 0
        errors: list[dict] = []

        for row_num, raw in enumerate(reader, start=2):
            try:
                raw_part_number = raw.get("part_number", "").strip() or None
                row = BulkImportRow(
                    part_name=raw.get("part_name", "").strip(),
                    part_number=raw_part_number,
                    category_name=raw.get("category_name", "").strip() or None,
                    barcode=raw.get("barcode", "").strip() or None,
                    unit_cost=Decimal(raw.get("unit_cost", "0") or "0"),
                    quantity=int(raw.get("quantity", 0) or 0),
                    low_stock_threshold=int(raw.get("low_stock_threshold", 10) or 10),
                )
            except Exception as e:
                errors.append({"row": row_num, "error": str(e)})
                continue

            # Resolve category
            category_id = None
            if row.category_name:
                cat = self.cat_repo.get_by_name(row.category_name)
                if not cat:
                    cat = InventoryCategory(category_name=row.category_name)
                    self.cat_repo.create(cat)
                category_id = cat.id

            # Try to match by part_number (if provided) or barcode
            existing = None
            if row.part_number:
                existing = self.inv_repo.get_by_part_number(row.part_number)
            if not existing and row.barcode:
                existing = self.inv_repo.get_by_barcode(row.barcode)

            if existing:
                existing.part_name = row.part_name
                if row.part_number:
                    existing.part_number = row.part_number
                existing.category_id = category_id
                if row.barcode:
                    existing.barcode = row.barcode
                existing.unit_cost = row.unit_cost
                existing.quantity = row.quantity
                existing.low_stock_threshold = row.low_stock_threshold
                self.inv_repo.save(existing)
                updated += 1
            else:
                item = InventoryItem(
                    part_name=row.part_name,
                    part_number=row.part_number,
                    category_id=category_id,
                    barcode=row.barcode,
                    unit_cost=row.unit_cost,
                    quantity=row.quantity,
                    low_stock_threshold=row.low_stock_threshold,
                )
                self.inv_repo.create(item)
                created += 1

        return {"created": created, "updated": updated, "errors": errors}

