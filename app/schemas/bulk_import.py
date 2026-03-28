from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.bulk_import import ImportFormat, ImportStatus, ImportType
from app.models.user import UserRole


# ─── Row-level schemas used during parsing ───────────────────────────────────

class StaffImportRow(BaseModel):
    """One staff row from a bulk import file."""

    name: str
    email: str
    phone: str | None = None
    role: UserRole = UserRole.staff

    @field_validator("email", mode="before")
    @classmethod
    def validate_email_format(cls, v: Any) -> str:
        """Validate email syntax without checking deliverability (allows .local TLDs)."""
        import re

        if not isinstance(v, str) or not re.match(
            r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v.strip()
        ):
            raise ValueError(f"'{v}' is not a valid email address format")
        return v.strip().lower()

    @field_validator("role", mode="before")
    @classmethod
    def coerce_role(cls, v: Any) -> UserRole:
        if isinstance(v, str):
            return UserRole(v.lower())
        return v


class InventoryImportRow(BaseModel):
    """One inventory row from a bulk import file (quantity-based model)."""

    part_name: str
    part_number: str
    category: str | None = None
    barcode: str | None = None
    quantity: int = 0
    unit_cost: Decimal = Decimal("0.00")

    @field_validator("unit_cost", mode="before")
    @classmethod
    def coerce_cost(cls, v: Any) -> Decimal:
        try:
            return Decimal(str(v))
        except Exception:
            return Decimal("0.00")

    @field_validator("quantity", mode="before")
    @classmethod
    def coerce_quantity(cls, v: Any) -> int:
        try:
            return int(str(v))
        except Exception:
            return 0


class CategoryImportRow(BaseModel):
    """One category row from a bulk import file."""

    category_name: str
    description: str | None = None


# ─── Response schemas ────────────────────────────────────────────────────────

class RowError(BaseModel):
    """Detail for a single row that failed during import."""

    row: int
    data: dict[str, Any]
    error: str


class BulkImportResponse(BaseModel):
    """Response returned after a bulk import completes (even partially)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    import_type: ImportType
    file_format: ImportFormat
    original_filename: str
    total_rows: int
    success_count: int
    failure_count: int
    status: ImportStatus
    error_details: list[dict[str, Any]] | None
    imported_by: UUID
    created_at: datetime


class BulkImportSummary(BaseModel):
    """Lightweight summary row for the import history list."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    import_type: ImportType
    file_format: ImportFormat
    original_filename: str
    total_rows: int
    success_count: int
    failure_count: int
    status: ImportStatus
    imported_by: UUID
    created_at: datetime
