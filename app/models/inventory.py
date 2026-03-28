from __future__ import annotations

import uuid
from datetime import datetime

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
    part_number: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
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
    low_stock_config: Mapped["LowStockConfig | None"] = relationship(
        "LowStockConfig",
        back_populates="inventory_item",
        uselist=False,
        lazy="select",
        cascade="all, delete-orphan",
    )

    @property
    def effective_threshold(self) -> int:
        if self.low_stock_config:
            return self.low_stock_config.threshold
        return self.low_stock_threshold

    @property
    def is_low_stock(self) -> bool:
        return self.quantity <= self.effective_threshold

    def __repr__(self) -> str:
        return f"<InventoryItem part={self.part_number} qty={self.quantity}>"


class LowStockConfig(Base, UUIDMixin, TimestampMixin):
    """Per-item override for low-stock threshold."""

    __tablename__ = "low_stock_configs"

    inventory_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inventory_items.id", ondelete="CASCADE"),
        nullable=True,
        unique=True,
        index=True,
    )
    threshold: Mapped[int] = mapped_column(Integer, nullable=False)
    configured_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
    )
    configured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    inventory_item: Mapped["InventoryItem | None"] = relationship(
        "InventoryItem", back_populates="low_stock_config", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<LowStockConfig item={self.inventory_item_id} threshold={self.threshold}>"
