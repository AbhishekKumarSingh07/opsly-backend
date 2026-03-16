from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import UUIDMixin, TimestampMixin


class ImportType(str, enum.Enum):
    inventory = "inventory"
    staff = "staff"


class ImportFormat(str, enum.Enum):
    xlsx = "xlsx"
    csv = "csv"
    json = "json"


class ImportStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"
    partial = "partial"
    failed = "failed"


class BulkImportLog(Base, UUIDMixin, TimestampMixin):
    """
    Tracks every bulk import session.
    Records who uploaded the file, format, row counts, and error details.
    """

    __tablename__ = "bulk_import_logs"

    imported_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    import_type: Mapped[ImportType] = mapped_column(
        Enum(ImportType, name="import_type_enum"), nullable=False
    )
    file_format: Mapped[ImportFormat] = mapped_column(
        Enum(ImportFormat, name="import_format_enum"), nullable=False
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)

    total_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    success_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    status: Mapped[ImportStatus] = mapped_column(
        Enum(ImportStatus, name="import_status_enum"),
        default=ImportStatus.pending,
        nullable=False,
    )

    # Full JSON detail of row-level errors: [{"row": int, "data": {}, "error": str}]
    error_details: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<BulkImportLog id={self.id} type={self.import_type} "
            f"status={self.status} success={self.success_count}/{self.total_rows}>"
        )
