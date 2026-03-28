from __future__ import annotations

"""
BulkImportService
-----------------
Handles parsing and importing of staff and inventory records from
.xlsx / .csv / .json files.

Partial imports are supported — valid rows are saved even when some rows fail.
"""

import csv
import io
import json
import logging
import secrets
import string
from decimal import Decimal
from typing import Any

from fastapi import UploadFile
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError
from app.core.permissions import PermissionPolicy
from app.core.security import hash_password
from app.models.bulk_import import BulkImportLog, ImportFormat, ImportStatus, ImportType
from app.models.inventory import InventoryItem
from app.models.user import User, UserRole
from app.repositories.inventory_repo import InventoryRepository
from app.repositories.user_repo import UserRepository
from app.schemas.bulk_import import (
    CategoryImportRow,
    InventoryImportRow,
    RowError,
    StaffImportRow,
)

logger = logging.getLogger("opsly.bulk_import")

# ─── Template definitions ────────────────────────────────────────────────────

STAFF_COLUMNS = ["name", "email", "phone", "role"]
INVENTORY_COLUMNS = ["part_name", "part_number", "category", "barcode", "quantity", "unit_cost"]
CATEGORY_COLUMNS = ["category_name", "description"]

STAFF_EXAMPLE_ROW = {
    "name": "Ravi Kumar",
    "email": "ravi.kumar@example.com",
    "phone": "9876543210",
    "role": "staff",
}
INVENTORY_EXAMPLE_ROW = {
    "part_name": "AVR Module",
    "part_number": "AVR-001",
    "category": "Electrical",
    "barcode": "BC123456",
    "quantity": "10",
    "unit_cost": "1500.00",
}
CATEGORY_EXAMPLE_ROW = {
    "category_name": "AVR",
    "description": "Automatic Voltage Regulators and components",
}

STAFF_INSTRUCTIONS = (
    "Required fields: name, email, role. "
    "Role must be 'staff' for moderator-initiated imports. "
    "phone is optional. "
    "A temporary password will be auto-generated for each user."
)
INVENTORY_INSTRUCTIONS = (
    "Required fields: part_name, part_number. "
    "barcode must be unique if provided. "
    "category will be created if it does not exist. "
    "quantity defaults to 0, unit_cost defaults to 0.00 if omitted."
)
CATEGORY_INSTRUCTIONS = (
    "Required fields: category_name. "
    "description is optional. "
    "Existing categories are updated (upsert by name)."
)


def _generate_temp_password(length: int = 12) -> str:
    """Generate a secure random temporary password."""
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    return "".join(secrets.choice(alphabet) for _ in range(length))


# ─── File parser ─────────────────────────────────────────────────────────────

def _parse_file(content: bytes, file_format: ImportFormat) -> list[dict[str, Any]]:
    """Parse raw file bytes into a list of row dicts."""
    if file_format == ImportFormat.json:
        data = json.loads(content.decode("utf-8"))
        if not isinstance(data, list):
            raise BusinessRuleError("INVALID_FORMAT", "JSON file must be a top-level array.")
        return data

    if file_format == ImportFormat.csv:
        text = content.decode("utf-8-sig")  # handle BOM
        reader = csv.DictReader(io.StringIO(text))
        return [dict(row) for row in reader]

    if file_format == ImportFormat.xlsx:
        try:
            import openpyxl  # type: ignore[import]
        except ImportError:
            raise BusinessRuleError(
                "MISSING_DEPENDENCY",
                "openpyxl is required for .xlsx imports. Install it with: pip install openpyxl",
            )
        wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return []
        headers = [str(h).strip() if h is not None else "" for h in rows[0]]
        return [dict(zip(headers, row)) for row in rows[1:] if any(v is not None for v in row)]

    raise BusinessRuleError("UNSUPPORTED_FORMAT", f"Unsupported format: {file_format}")


def _detect_format(filename: str) -> ImportFormat:
    ext = filename.rsplit(".", 1)[-1].lower()
    mapping = {"xlsx": ImportFormat.xlsx, "csv": ImportFormat.csv, "json": ImportFormat.json}
    if ext not in mapping:
        raise BusinessRuleError(
            "UNSUPPORTED_FORMAT",
            f"Unsupported file extension '.{ext}'. Accepted: xlsx, csv, json",
        )
    return mapping[ext]


# ─── Service class ────────────────────────────────────────────────────────────

class BulkImportService:
    """Orchestrates bulk import of staff and inventory records."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.user_repo = UserRepository(db)
        self.inv_repo = InventoryRepository(db)

    # ── Public entry points ───────────────────────────────────────────────────

    async def import_staff(self, file: UploadFile, actor: User) -> BulkImportLog:
        """
        Parse and import staff records from an uploaded file.
        Moderators may only create staff-role accounts — any row attempting to
        create a moderator is rejected with a clear error message.
        """
        PermissionPolicy(actor).require_can_bulk_import()

        content = await file.read()
        file_format = _detect_format(file.filename or "upload.csv")
        rows = _parse_file(content, file_format)

        log = self._create_log(actor, ImportType.staff, file_format, file.filename or "", len(rows))

        errors: list[RowError] = []
        success = 0

        for idx, row_data in enumerate(rows, start=1):
            row_data = {k: (v if v != "" else None) for k, v in (row_data or {}).items()}
            try:
                row = StaffImportRow.model_validate(row_data)
                # Policy: moderators cannot import non-staff roles
                PermissionPolicy(actor).require_can_create_user(row.role)

                existing_user = self.user_repo.get_by_email(row.email)
                if existing_user:
                    # Update existing user instead of failing
                    existing_user.name = row.name
                    existing_user.phone = row.phone
                    existing_user.role = row.role
                    self.db.flush()
                    success += 1
                    logger.info("Bulk import: updated existing user %s (row %d)", row.email, idx)
                    continue

                temp_password = _generate_temp_password()
                user = User(
                    name=row.name,
                    email=row.email,
                    phone=row.phone,
                    role=row.role,
                    hashed_password=hash_password(temp_password),
                    must_change_password=True,
                    created_by=actor.id,
                )
                self.db.add(user)
                self.db.flush()
                success += 1
                logger.info("Bulk import: created user %s (row %d)", row.email, idx)

            except (ValidationError, ValueError, Exception) as exc:
                errors.append(RowError(row=idx, data=row_data, error=str(exc)))
                logger.warning("Bulk import staff row %d failed: %s", idx, exc)

        self._finalise_log(log, success, errors)
        return log

    async def import_inventory(self, file: UploadFile, actor: User) -> BulkImportLog:
        """Parse and import inventory items from an uploaded file (quantity-based model)."""
        PermissionPolicy(actor).require_can_bulk_import()

        content = await file.read()
        file_format = _detect_format(file.filename or "upload.csv")
        rows = _parse_file(content, file_format)

        log = self._create_log(actor, ImportType.inventory, file_format, file.filename or "", len(rows))

        errors: list[RowError] = []
        success = 0

        for idx, row_data in enumerate(rows, start=1):
            row_data = {k: (v if v != "" else None) for k, v in (row_data or {}).items()}
            try:
                row = InventoryImportRow.model_validate(row_data)

                # Resolve or create category
                category_id = None
                if row.category:
                    from app.models.inventory import InventoryCategory
                    cat = (
                        self.db.query(InventoryCategory)
                        .filter(
                            InventoryCategory.category_name == row.category,
                            InventoryCategory.is_deleted.is_(False),
                        )
                        .first()
                    )
                    if cat is None:
                        cat = InventoryCategory(category_name=row.category)
                        self.db.add(cat)
                        self.db.flush()
                    category_id = cat.id

                existing: InventoryItem | None = None
                if row.barcode:
                    existing = self.inv_repo.get_by_barcode(row.barcode)
                if existing is None:
                    existing = self.inv_repo.get_by_part_number(row.part_number)

                if existing is not None:
                    # Update the existing item instead of failing
                    existing.part_name = row.part_name
                    existing.part_number = row.part_number
                    if category_id is not None:
                        existing.category_id = category_id
                    if row.barcode is not None:
                        existing.barcode = row.barcode
                    if row.unit_cost is not None:
                        existing.unit_cost = row.unit_cost
                    if row.quantity is not None:
                        existing.quantity = row.quantity
                    self.db.flush()
                    success += 1
                    logger.info(
                        "Bulk import: updated existing inventory item %s (row %d)",
                        row.part_number, idx,
                    )
                    continue

                item = InventoryItem(
                    part_name=row.part_name,
                    part_number=row.part_number,
                    category_id=category_id,
                    barcode=row.barcode,
                    unit_cost=row.unit_cost or Decimal("0.00"),
                    quantity=row.quantity or 0,
                )
                self.db.add(item)
                self.db.flush()
                success += 1
                logger.info("Bulk import: created inventory item %s (row %d)", row.part_number, idx)

            except (ValidationError, ValueError, Exception) as exc:
                errors.append(RowError(row=idx, data=row_data, error=str(exc)))
                logger.warning("Bulk import inventory row %d failed: %s", idx, exc)

        self._finalise_log(log, success, errors)
        return log

    async def import_categories(self, file: UploadFile, actor: User) -> BulkImportLog:
        """Parse and import inventory categories from an uploaded file (upsert by name)."""
        from app.models.inventory import InventoryCategory

        PermissionPolicy(actor).require_can_bulk_import()

        content = await file.read()
        file_format = _detect_format(file.filename or "upload.csv")
        rows = _parse_file(content, file_format)

        log = self._create_log(actor, ImportType.categories, file_format, file.filename or "", len(rows))

        errors: list[RowError] = []
        success = 0

        for idx, row_data in enumerate(rows, start=1):
            row_data = {k: (v if v != "" else None) for k, v in (row_data or {}).items()}
            try:
                row = CategoryImportRow.model_validate(row_data)

                existing = (
                    self.db.query(InventoryCategory)
                    .filter(
                        InventoryCategory.category_name == row.category_name,
                        InventoryCategory.is_deleted.is_(False),
                    )
                    .first()
                )

                if existing is not None:
                    # Update description if provided
                    if row.description is not None:
                        existing.description = row.description
                    self.db.flush()
                    success += 1
                    logger.info(
                        "Bulk import: updated existing category '%s' (row %d)",
                        row.category_name, idx,
                    )
                else:
                    cat = InventoryCategory(
                        category_name=row.category_name,
                        description=row.description,
                    )
                    self.db.add(cat)
                    self.db.flush()
                    success += 1
                    logger.info("Bulk import: created category '%s' (row %d)", row.category_name, idx)

            except (ValidationError, ValueError, Exception) as exc:
                errors.append(RowError(row=idx, data=row_data, error=str(exc)))
                logger.warning("Bulk import category row %d failed: %s", idx, exc)

        self._finalise_log(log, success, errors)
        return log

    # ── Template generation ───────────────────────────────────────────────────

    @staticmethod
    def get_staff_template_csv() -> str:
        """Return a CSV template string for staff import."""
        lines = [
            "# Staff Import Template — Required: name, email, role | Optional: phone",
            "# role must be one of: staff (moderators can only use 'staff')",
            ",".join(STAFF_COLUMNS),
            ",".join(str(STAFF_EXAMPLE_ROW[c]) for c in STAFF_COLUMNS),
        ]
        return "\n".join(lines)

    @staticmethod
    def get_inventory_template_csv() -> str:
        """Return a CSV template string for inventory import."""
        lines = [
            "# Inventory Import Template — Required: part_name, part_number | Optional: category, barcode, quantity, unit_cost",
            "# barcode must be globally unique if provided | quantity defaults to 0 | unit_cost defaults to 0.00",
            ",".join(INVENTORY_COLUMNS),
            ",".join(str(INVENTORY_EXAMPLE_ROW[c]) for c in INVENTORY_COLUMNS),
        ]
        return "\n".join(lines)

    @staticmethod
    def get_categories_template_csv() -> str:
        """Return a CSV template string for category import."""
        lines = [
            "# Categories Import Template — Required: category_name | Optional: description",
            "# Existing categories are updated (upsert by name)",
            ",".join(CATEGORY_COLUMNS),
            ",".join(str(CATEGORY_EXAMPLE_ROW[c]) for c in CATEGORY_COLUMNS),
        ]
        return "\n".join(lines)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _create_log(
        self,
        actor: User,
        import_type: ImportType,
        file_format: ImportFormat,
        filename: str,
        total_rows: int,
    ) -> BulkImportLog:
        log = BulkImportLog(
            imported_by=actor.id,
            import_type=import_type,
            file_format=file_format,
            original_filename=filename,
            total_rows=total_rows,
            status=ImportStatus.pending,
        )
        self.db.add(log)
        self.db.flush()
        return log

    def _finalise_log(self, log: BulkImportLog, success: int, errors: list[RowError]) -> None:
        log.success_count = success
        log.failure_count = len(errors)
        log.error_details = [e.model_dump() for e in errors] if errors else None

        if success == 0 and errors:
            log.status = ImportStatus.failed
        elif errors:
            log.status = ImportStatus.partial
        else:
            log.status = ImportStatus.completed

        self.db.flush()
