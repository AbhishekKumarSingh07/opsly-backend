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
    part_number: str
    category_id: UUID | None = None
    barcode: str | None = None
    unit_cost: Decimal = Decimal("0.00")
    quantity: int = 0
    low_stock_threshold: int = 10


class InventoryItemUpdate(BaseModel):
    part_name: str | None = None
    category_id: UUID | None = None
    barcode: str | None = None
    unit_cost: Decimal | None = None
    quantity: int | None = None
    low_stock_threshold: int | None = None


class InventoryItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    part_name: str
    part_number: str
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


# ─── Low Stock Config ────────────────────────────────────────────────────────

class LowStockConfigCreate(BaseModel):
    inventory_item_id: UUID
    threshold: int

    @field_validator("threshold")
    @classmethod
    def threshold_positive(cls, v: int) -> int:
        if v < 0:
            raise ValueError("threshold must be >= 0")
        return v


class LowStockConfigUpdate(BaseModel):
    threshold: int

    @field_validator("threshold")
    @classmethod
    def threshold_positive(cls, v: int) -> int:
        if v < 0:
            raise ValueError("threshold must be >= 0")
        return v


class LowStockConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    inventory_item_id: UUID | None
    part_number: str | None = None
    part_name: str | None = None
    threshold: int
    configured_by: UUID
    configured_at: datetime


# ─── Bulk Import ─────────────────────────────────────────────────────────────

class BulkImportRow(BaseModel):
    part_name: str
    part_number: str
    category_name: str | None = None
    barcode: str | None = None
    unit_cost: Decimal = Decimal("0.00")
    quantity: int = 0
    low_stock_threshold: int = 10
