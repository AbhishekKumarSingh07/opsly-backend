from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DECIMAL, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import AuditMixin, UUIDMixin, TimestampMixin


class InventoryItemStatus(str, enum.Enum):
    IN_STOCK = "IN_STOCK"
    CHECKED_OUT = "CHECKED_OUT"
    PENDING_RETURN = "PENDING_RETURN"
    CONSUMED = "CONSUMED"
    DISPOSED = "DISPOSED"


class InventoryItem(Base, AuditMixin):
    """Serialized / individually-tracked inventory part."""

    __tablename__ = "inventory_items"

    part_name: Mapped[str] = mapped_column(String(255), nullable=False)
    part_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    serial_no: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    barcode: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    unit_cost: Mapped[Decimal] = mapped_column(DECIMAL(12, 2), nullable=False, default=Decimal("0.00"))

    status: Mapped[InventoryItemStatus] = mapped_column(
        Enum(InventoryItemStatus, name="inventory_item_status_enum"),
        default=InventoryItemStatus.IN_STOCK,
        nullable=False,
    )

    current_ticket_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tickets.id", ondelete="SET NULL"),
        nullable=True,
    )
    checked_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    checked_out_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    received_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    current_ticket: Mapped["Ticket | None"] = relationship(
        "Ticket", back_populates="inventory_items", foreign_keys=[current_ticket_id], lazy="select"
    )
    movements: Mapped[list["InventoryMovement"]] = relationship(
        "InventoryMovement", back_populates="item", lazy="select", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<InventoryItem part={self.part_number} barcode={self.barcode} status={self.status}>"


class InventoryMovement(Base, UUIDMixin):
    """Audit trail for every status change of a serialized inventory item."""

    __tablename__ = "inventory_movements"

    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inventory_items.id"), nullable=False, index=True
    )
    from_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    to_status: Mapped[str] = mapped_column(String(50), nullable=False)
    ticket_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tickets.id", ondelete="SET NULL"), nullable=True
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    item: Mapped["InventoryItem | None"] = relationship("InventoryItem", back_populates="movements")

    def __repr__(self) -> str:
        return f"<InventoryMovement item={self.item_id} {self.from_status}→{self.to_status}>"


class InventoryStock(Base, AuditMixin):
    """Bulk (non-serialized) stock items, e.g., coolant, cables (sold by quantity)."""

    __tablename__ = "inventory_stock"

    part_name: Mapped[str] = mapped_column(String(255), nullable=False)
    part_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    unit: Mapped[str] = mapped_column(String(50), nullable=False, default="piece")
    quantity_in_stock: Mapped[Decimal] = mapped_column(DECIMAL(12, 3), nullable=False, default=Decimal("0"))
    reorder_level: Mapped[Decimal] = mapped_column(DECIMAL(12, 3), nullable=False, default=Decimal("0"))
    unit_cost: Mapped[Decimal] = mapped_column(DECIMAL(12, 2), nullable=False, default=Decimal("0.00"))
    last_updated: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<InventoryStock part={self.part_number} qty={self.quantity_in_stock}>"
