from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import AuditMixin


class Client(Base, AuditMixin):
    """External client / customer record."""

    __tablename__ = "clients"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_person: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    portal_password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    portal_enabled: Mapped[bool] = mapped_column(default=False, server_default="false")

    sites: Mapped[list["Site"]] = relationship("Site", back_populates="client", lazy="select")

    def __repr__(self) -> str:
        return f"<Client id={self.id} name={self.name}>"
