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
    InventoryItem,
    LowStockConfig,
)
from app.models.user import User
from app.repositories.inventory_repo import (
    CategoryRepository,
    InventoryRepository,
    LowStockConfigRepository,
)
from app.schemas.inventory import (
    BulkImportRow,
    CategoryCreate,
    CategoryUpdate,
    InventoryItemCreate,
    InventoryItemUpdate,
    LowStockConfigCreate,
    LowStockConfigUpdate,
)


class InventoryService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.cat_repo = CategoryRepository(db)
        self.inv_repo = InventoryRepository(db)
        self.config_repo = LowStockConfigRepository(db)

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
        if self.inv_repo.get_by_part_number(payload.part_number):
            raise ConflictError(f"Part number '{payload.part_number}' already exists.")
        if payload.barcode and self.inv_repo.get_by_barcode(payload.barcode):
            raise ConflictError(f"Barcode '{payload.barcode}' already exists.")
        item = InventoryItem(
            part_name=payload.part_name,
            part_number=payload.part_number,
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
        if payload.barcode and payload.barcode != item.barcode:
            if self.inv_repo.get_by_barcode(payload.barcode):
                raise ConflictError(f"Barcode '{payload.barcode}' already exists.")
        for field in ("part_name", "category_id", "barcode", "unit_cost", "quantity", "low_stock_threshold"):
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

    # ── Low Stock Config ──────────────────────────────────────────────────────

    def set_low_stock_config(self, payload: LowStockConfigCreate, actor: User) -> LowStockConfig:
        item = self.inv_repo.get_by_id(payload.inventory_item_id)
        if not item or item.is_deleted:
            raise NotFoundError("InventoryItem", str(payload.inventory_item_id))
        existing = self.config_repo.get_by_item(payload.inventory_item_id)
        if existing:
            existing.threshold = payload.threshold
            existing.configured_by = actor.id
            existing.configured_at = datetime.now(timezone.utc)
            return self.config_repo.save(existing)
        config = LowStockConfig(
            inventory_item_id=payload.inventory_item_id,
            threshold=payload.threshold,
            configured_by=actor.id,
            configured_at=datetime.now(timezone.utc),
        )
        return self.config_repo.create(config)

    def update_low_stock_config(self, config_id: UUID, payload: LowStockConfigUpdate, actor: User) -> LowStockConfig:
        config = self.config_repo.get_by_id(config_id)
        if not config:
            raise NotFoundError("LowStockConfig", str(config_id))
        config.threshold = payload.threshold
        config.configured_by = actor.id
        config.configured_at = datetime.now(timezone.utc)
        return self.config_repo.save(config)

    def delete_low_stock_config(self, config_id: UUID) -> None:
        config = self.config_repo.get_by_id(config_id)
        if not config:
            raise NotFoundError("LowStockConfig", str(config_id))
        self.db.delete(config)
        self.db.flush()

    # ── Bulk Import ───────────────────────────────────────────────────────────

    def bulk_import_csv(self, csv_content: bytes, actor: User) -> dict:
        text = csv_content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        created = 0
        updated = 0
        errors: list[dict] = []

        for row_num, raw in enumerate(reader, start=2):
            try:
                row = BulkImportRow(
                    part_name=raw.get("part_name", "").strip(),
                    part_number=raw.get("part_number", "").strip(),
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

            existing = self.inv_repo.get_by_part_number(row.part_number)
            if existing:
                existing.part_name = row.part_name
                existing.category_id = category_id
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
