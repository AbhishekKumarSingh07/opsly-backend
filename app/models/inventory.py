from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DECIMAL, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import AuditMixin, UUIDMixin, TimestampMixin


class InventoryCategory(Base, AuditMixin):
    """Category for grouping inventory items (e.g. AVR, Battery, Breaker)."""

    __tablename__ = "inventory_categories"

    category_name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    items: Mapped[list["InventoryItem"]] = relationship(
        "InventoryItem", back_populates="category", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<InventoryCategory name={self.category_name}>"


class InventoryItem(Base, AuditMixin):
    """Inventory item with quantity tracking."""

    __tablename__ = "inventory_items"

    part_name: Mapped[str] = mapped_column(String(255), nullable=False)
    part_number: Mapped[str | None] = mapped_column(
        String(100), nullable=True, unique=True, index=True
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inventory_categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    barcode: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True, index=True)
    unit_cost: Mapped[float] = mapped_column(DECIMAL(12, 2), nullable=False, default=0.0)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    low_stock_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=10)

    category: Mapped["InventoryCategory | None"] = relationship(
        "InventoryCategory", back_populates="items", lazy="select"
    )
    dispatches: Mapped[list["InventoryDispatch"]] = relationship(
        "InventoryDispatch", back_populates="inventory_item", lazy="dynamic"
    )

    @property
    def effective_threshold(self) -> int:
        return self.low_stock_threshold

    @property
    def is_low_stock(self) -> bool:
        return self.quantity <= self.low_stock_threshold

    def __repr__(self) -> str:
        return f"<InventoryItem part={self.part_number} qty={self.quantity}>"


class InventoryDispatch(Base, UUIDMixin, TimestampMixin):
    """Records a dispatch of inventory items to a ticket."""

    __tablename__ = "inventory_dispatches"

    inventory_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inventory_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    dispatched_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
    )
    dispatched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    part_number_dispatched: Mapped[str | None] = mapped_column(String(100), nullable=True)
    barcode_dispatched: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Return tracking
    returned_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    returned_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    inventory_item: Mapped["InventoryItem"] = relationship(
        "InventoryItem", back_populates="dispatches", lazy="select"
    )
    ticket: Mapped["Ticket"] = relationship("Ticket", lazy="select")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return (
            f"<InventoryDispatch item={self.inventory_item_id} "
            f"ticket={self.ticket_id} qty={self.quantity}>"
        )
