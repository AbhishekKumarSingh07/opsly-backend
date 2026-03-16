from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.inventory import InventoryItemStatus


class InventoryIntakeSchema(BaseModel):
    """Request body for receiving a new part into inventory."""

    model_config = ConfigDict(from_attributes=True)

    part_name: str
    part_number: str
    serial_no: str | None = None
    barcode: str | None = None
    description: str | None = None
    unit_cost: Decimal = Decimal("0.00")


class InventoryCheckoutSchema(BaseModel):
    """Request body for checking out a part to a ticket."""

    model_config = ConfigDict(from_attributes=True)

    item_id: UUID
    ticket_id: UUID


class InventoryReturnSchema(BaseModel):
    """Request body for scanning a returned part."""

    model_config = ConfigDict(from_attributes=True)

    barcode: str
    notes: str | None = None


class InventoryItemResponse(BaseModel):
    """Inventory item response model."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    part_name: str
    part_number: str
    serial_no: str | None
    barcode: str | None
    description: str | None
    unit_cost: Decimal
    status: InventoryItemStatus
    current_ticket_id: UUID | None
    checked_out_at: datetime | None
    checked_out_by: UUID | None
    returned_at: datetime | None
    received_by: UUID | None
    created_at: datetime


class InventoryStockResponse(BaseModel):
    """Bulk stock item response model."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    part_name: str
    part_number: str
    unit: str
    quantity_in_stock: Decimal
    reorder_level: Decimal
    unit_cost: Decimal
    last_updated: datetime | None
