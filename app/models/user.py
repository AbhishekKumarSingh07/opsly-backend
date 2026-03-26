from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import UUIDMixin, TimestampMixin


class UserRole(str, enum.Enum):
    owner = "owner"
    moderator = "moderator"
    staff = "staff"
    technician = "technician"


class User(Base, UUIDMixin, TimestampMixin):
    """Represents an Opsly platform user (owner / moderator / staff)."""

    __tablename__ = "users"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(20), unique=True, nullable=True)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role_enum"), nullable=False, default=UserRole.staff
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Force password change on first login (used for bulk-imported / reset accounts)
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )

    # Track who created this user (owner or moderator)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    # Relationships
    assigned_tickets: Mapped[list["Ticket"]] = relationship(
        "Ticket",
        secondary="ticket_technicians",
        back_populates="technicians",
        lazy="select",
    )
    attendance_records: Mapped[list["Attendance"]] = relationship(
        "Attendance",
        back_populates="user",
        lazy="select",
        foreign_keys="Attendance.user_id",
    )
    created_tickets: Mapped[list["Ticket"]] = relationship(
        "Ticket",
        back_populates="creator",
        lazy="select",
        foreign_keys="Ticket.created_by",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} role={self.role}>"
