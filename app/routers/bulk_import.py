from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.exceptions import NotFoundError
from app.repositories.bulk_import_repo import BulkImportRepository
from app.schemas.bulk_import import BulkImportResponse, BulkImportSummary
from app.services.bulk_import_service import BulkImportService

router = APIRouter(prefix="/imports", tags=["Bulk Import"])

_ACCEPTED_MIME = {
    "text/csv",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/json",
    "application/octet-stream",  # some browsers send xlsx as this
    "text/plain",                # some browsers send csv as this
}


@router.post("/staff", response_model=BulkImportResponse)
async def import_staff(
    file: UploadFile = File(..., description="Excel (.xlsx), CSV (.csv) or JSON (.json) file"),
    current_user=Depends(require_role("owner", "moderator")),
    db: Session = Depends(get_db),
):
    """
    Bulk-import staff members from a file.

    Rules:
    - Owner can import any role (owner / moderator / staff).
    - Moderator can only import staff-role accounts; rows with other roles are rejected.
    - Each imported user gets an auto-generated temporary password.
    - Imported users are flagged must_change_password=True.
    - Partial imports are supported — valid rows are saved even when some rows fail.
    - Accepted formats: .xlsx, .csv, .json

    Accessible by: owner, moderator.
    """
    service = BulkImportService(db)
    log = await service.import_staff(file, current_user)
    return log


@router.post("/inventory", response_model=BulkImportResponse)
async def import_inventory(
    file: UploadFile = File(..., description="Excel (.xlsx), CSV (.csv) or JSON (.json) file"),
    current_user=Depends(require_role("owner", "moderator")),
    db: Session = Depends(get_db),
):
    """
    Bulk-import inventory items from a file.

    - Rows with duplicate barcodes or serial numbers are rejected with a clear error.
    - Partial imports are supported.
    - Accepted formats: .xlsx, .csv, .json

    Accessible by: owner, moderator.
    """
    service = BulkImportService(db)
    log = await service.import_inventory(file, current_user)
    return log


@router.post("/categories", response_model=BulkImportResponse)
async def import_categories(
    file: UploadFile = File(..., description="Excel (.xlsx), CSV (.csv) or JSON (.json) file"),
    current_user=Depends(require_role("owner", "moderator")),
    db: Session = Depends(get_db),
):
    """
    Bulk-import inventory categories from a file.

    - Existing categories (matched by name) are updated (upsert).
    - New categories are created automatically.
    - Partial imports are supported.
    - Accepted formats: .xlsx, .csv, .json

    Accessible by: owner, moderator.
    """
    service = BulkImportService(db)
    log = await service.import_categories(file, current_user)
    return log


# ── Static GET routes MUST come before /{import_id} to avoid route shadowing ──

@router.get("/format-reference", include_in_schema=True)
def format_reference(
    current_user=Depends(require_role("owner", "moderator")),
):
    """
    Return the expected format specification for all import types.

    Use this in the UI to show users the column names, types, and rules before
    they upload a file — regardless of whether they choose Excel, CSV, or JSON.

    Accessible by: owner, moderator.
    """
    return {
        "staff": [
            {"column": "name",  "type": "string",  "required": True,  "notes": "Full name of the staff member"},
            {"column": "email", "type": "string",  "required": True,  "notes": "Must be a valid email, globally unique"},
            {"column": "phone", "type": "string",  "required": False, "notes": "10-digit mobile number"},
            {"column": "role",  "type": "enum",    "required": True,  "notes": "Allowed: staff (moderators cannot use moderator/owner)"},
        ],
        "inventory": [
            {"column": "part_name",   "type": "string",  "required": True,  "notes": "Descriptive name of the part"},
            {"column": "part_number", "type": "string",  "required": True,  "notes": "Internal part number, must be unique"},
            {"column": "category",    "type": "string",  "required": False, "notes": "Category name — created automatically if it does not exist"},
            {"column": "barcode",     "type": "string",  "required": False, "notes": "Must be globally unique if provided"},
            {"column": "quantity",    "type": "integer", "required": False, "notes": "Stock quantity, defaults to 0"},
            {"column": "unit_cost",   "type": "decimal", "required": False, "notes": "Cost in INR, defaults to 0.00"},
        ],
        "categories": [
            {"column": "category_name", "type": "string", "required": True,  "notes": "Name of the category — upserted if it already exists"},
            {"column": "description",   "type": "string", "required": False, "notes": "Optional description of the category"},
        ],
    }


@router.get("/templates/staff", response_class=PlainTextResponse)
def download_staff_template(
    current_user=Depends(require_role("owner", "moderator")),
):
    """
    Download the CSV template for staff imports.

    Includes column headers, an example row, and instructions.
    Accessible by: owner, moderator.
    """
    return PlainTextResponse(
        content=BulkImportService.get_staff_template_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=staff_import_template.csv"},
    )


@router.get("/templates/inventory", response_class=PlainTextResponse)
def download_inventory_template(
    current_user=Depends(require_role("owner", "moderator")),
):
    """
    Download the CSV template for inventory imports.

    Includes column headers, an example row, and instructions.
    Accessible by: owner, moderator.
    """
    return PlainTextResponse(
        content=BulkImportService.get_inventory_template_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=inventory_import_template.csv"},
    )


@router.get("/templates/categories", response_class=PlainTextResponse)
def download_categories_template(
    current_user=Depends(require_role("owner", "moderator")),
):
    """
    Download the CSV template for category imports.

    Includes column headers, an example row, and instructions.
    Accessible by: owner, moderator.
    """
    return PlainTextResponse(
        content=BulkImportService.get_categories_template_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=categories_import_template.csv"},
    )


@router.get("/", response_model=list[BulkImportSummary])
def list_import_history(
    skip: int = 0,
    limit: int = 50,
    current_user=Depends(require_role("owner", "moderator")),
    db: Session = Depends(get_db),
):
    """
    List all past bulk import sessions ordered by most recent first.

    - Owner sees all imports.
    - Moderator sees only their own imports.
    - Accessible by: owner, moderator.
    """
    from app.models.user import UserRole

    repo = BulkImportRepository(db)
    if current_user.role == UserRole.owner:
        return repo.list_all_ordered(skip=skip, limit=limit)
    return repo.list_by_actor(current_user.id, skip=skip, limit=limit)


@router.get("/{import_id}", response_model=BulkImportResponse)
def get_import_detail(
    import_id: UUID,
    current_user=Depends(require_role("owner", "moderator")),
    db: Session = Depends(get_db),
):
    """
    Retrieve full detail (including per-row errors) for a single import session.

    - Owner can view any import.
    - Moderator can only view their own imports.
    - Accessible by: owner, moderator.
    """
    from app.models.user import UserRole

    repo = BulkImportRepository(db)
    log = repo.get_by_id(import_id)
    if not log:
        raise NotFoundError("BulkImportLog", str(import_id))
    if current_user.role != UserRole.owner and log.imported_by != current_user.id:
        raise NotFoundError("BulkImportLog", str(import_id))  # 404 — do not reveal existence
    return log
