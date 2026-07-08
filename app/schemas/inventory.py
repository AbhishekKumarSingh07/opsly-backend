from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


# ─── Category ────────────────────────────────────────────────────────────────

class CategoryCreate(BaseModel):
    category_name: str
    description: str | None = None


class CategoryUpdate(BaseModel):
    category_name: str | None = None
    description: str | None = None


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    category_name: str
    description: str | None
    item_count: int = 0
    created_at: datetime
    updated_at: datetime


# ─── Inventory Item ───────────────────────────────────────────────────────────

class InventoryItemCreate(BaseModel):
    part_name: str
    part_number: str | None = None
    category_id: UUID | None = None
    barcode: str | None = None
    unit_cost: Decimal = Decimal("0.00")
    quantity: int = 0
    low_stock_threshold: int = 10


class InventoryItemUpdate(BaseModel):
    part_name: str | None = None
    part_number: str | None = None
    category_id: UUID | None = None
    barcode: str | None = None
    unit_cost: Decimal | None = None
    quantity: int | None = None
    low_stock_threshold: int | None = None


class InventoryItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    part_name: str
    part_number: str | None
    category_id: UUID | None
    category_name: str | None = None
    barcode: str | None
    unit_cost: Decimal
    quantity: int
    low_stock_threshold: int
    effective_threshold: int
    is_low_stock: bool
    created_at: datetime
    updated_at: datetime


# ─── Inventory Dispatch ───────────────────────────────────────────────────────

class InventoryDispatchCreate(BaseModel):
    inventory_item_id: UUID
    ticket_id: UUID
    quantity: int
    notes: str | None = None

    @field_validator("quantity")
    @classmethod
    def quantity_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("quantity must be > 0")
        return v


class InventoryDispatchReturn(BaseModel):
    returned_quantity: int

    @field_validator("returned_quantity")
    @classmethod
    def qty_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("returned_quantity must be > 0")
        return v


class InventoryDispatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    inventory_item_id: UUID
    ticket_id: UUID
    quantity: int
    dispatched_by: UUID
    dispatched_at: datetime
    part_number_dispatched: str | None
    barcode_dispatched: str | None
    notes: str | None
    returned_quantity: int
    returned_by: UUID | None
    returned_at: datetime | None
    created_at: datetime
    updated_at: datetime
    # Enriched fields (populated by router)
    item_name: str | None = None
    ticket_ref: str | None = None


# ─── Bulk Import ─────────────────────────────────────────────────────────────

class BulkImportRow(BaseModel):
    part_name: str
    part_number: str | None = None
    category_name: str | None = None
    barcode: str | None = None
    unit_cost: Decimal = Decimal("0.00")
    quantity: int = 0
    low_stock_threshold: int = 10
