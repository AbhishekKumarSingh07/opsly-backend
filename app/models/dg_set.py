from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import AuditMixin


class DGSet(Base, AuditMixin):
    """Diesel Generator set belonging to a site/client."""

    __tablename__ = "dg_sets"

    site_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="SET NULL"),
        nullable=True,
    )
    make: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    capacity_kva: Mapped[float | None] = mapped_column(Float, nullable=True)
    serial_no: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    installation_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_service_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    next_service_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    amc_expiry: Mapped[date | None] = mapped_column(Date, nullable=True)
    service_interval_days: Mapped[int] = mapped_column(Integer, default=90, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    site: Mapped["Site | None"] = relationship("Site", back_populates="dg_sets", lazy="select")
    tickets: Mapped[list["Ticket"]] = relationship("Ticket", back_populates="dg_set", lazy="select")

    def __repr__(self) -> str:
        return f"<DGSet id={self.id} serial={self.serial_no}>"
