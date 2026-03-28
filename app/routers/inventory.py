from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db, require_role
from app.repositories.inventory_repo import (
    CategoryRepository,
    InventoryRepository,
    LowStockConfigRepository,
)
from app.schemas.common import PaginatedResponse
from app.schemas.inventory import (
    CategoryCreate,
    CategoryResponse,
    CategoryUpdate,
    InventoryItemCreate,
    InventoryItemResponse,
    InventoryItemUpdate,
    LowStockConfigCreate,
    LowStockConfigResponse,
    LowStockConfigUpdate,
)
from app.services.inventory_service import InventoryService
from app.utils.pagination import paginate, page_offset

router = APIRouter(prefix="/inventory", tags=["Inventory"])


def _item_response(item) -> InventoryItemResponse:
    return InventoryItemResponse(
        id=item.id,
        part_name=item.part_name,
        part_number=item.part_number,
        category_id=item.category_id,
        category_name=item.category.category_name if item.category else None,
        barcode=item.barcode,
        unit_cost=item.unit_cost,
        quantity=item.quantity,
        low_stock_threshold=item.low_stock_threshold,
        effective_threshold=item.effective_threshold,
        is_low_stock=item.is_low_stock,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


# ── Categories ────────────────────────────────────────────────────────────────

@router.post("/categories", response_model=CategoryResponse)
def create_category(
    payload: CategoryCreate,
    current_user=Depends(require_role("owner")),
    db: Session = Depends(get_db),
):
    svc = InventoryService(db)
    cat = svc.create_category(payload, current_user)
    item_count = CategoryRepository(db).item_count(cat.id)
    return CategoryResponse(
        id=cat.id,
        category_name=cat.category_name,
        description=cat.description,
        item_count=item_count,
        created_at=cat.created_at,
        updated_at=cat.updated_at,
    )


@router.get("/categories", response_model=list[CategoryResponse])
def list_categories(
    _=Depends(require_role("owner", "moderator")),
    db: Session = Depends(get_db),
):
    rows = CategoryRepository(db).list_all_with_counts()
    return [
        CategoryResponse(
            id=cat.id,
            category_name=cat.category_name,
            description=cat.description,
            item_count=cnt,
            created_at=cat.created_at,
            updated_at=cat.updated_at,
        )
        for cat, cnt in rows
    ]


@router.put("/categories/{cat_id}", response_model=CategoryResponse)
def update_category(
    cat_id: UUID,
    payload: CategoryUpdate,
    current_user=Depends(require_role("owner")),
    db: Session = Depends(get_db),
):
    svc = InventoryService(db)
    cat = svc.update_category(cat_id, payload, current_user)
    item_count = CategoryRepository(db).item_count(cat.id)
    return CategoryResponse(
        id=cat.id,
        category_name=cat.category_name,
        description=cat.description,
        item_count=item_count,
        created_at=cat.created_at,
        updated_at=cat.updated_at,
    )


@router.delete("/categories/{cat_id}", status_code=204)
def delete_category(
    cat_id: UUID,
    current_user=Depends(require_role("owner")),
    db: Session = Depends(get_db),
):
    InventoryService(db).delete_category(cat_id, current_user)


# ── Inventory Items ───────────────────────────────────────────────────────────

@router.post("/", response_model=InventoryItemResponse)
def create_item(
    payload: InventoryItemCreate,
    current_user=Depends(require_role("owner", "moderator")),
    db: Session = Depends(get_db),
):
    return _item_response(InventoryService(db).create_item(payload, current_user))


@router.get("/", response_model=PaginatedResponse[InventoryItemResponse])
def list_inventory(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category_id: UUID | None = Query(None),
    search: str | None = Query(None),
    low_stock_only: bool = Query(False),
    _=Depends(require_role("owner", "moderator")),
    db: Session = Depends(get_db),
):
    repo = InventoryRepository(db)
    skip, limit = page_offset(page, page_size)
    items = repo.list_filtered(skip=skip, limit=limit, category_id=category_id, search=search, low_stock_only=low_stock_only)
    total = repo.count_filtered(category_id=category_id, search=search, low_stock_only=low_stock_only)
    return paginate([_item_response(i) for i in items], total=total, page=page, page_size=page_size)


@router.get("/low-stock", response_model=list[InventoryItemResponse])
def get_low_stock(
    _=Depends(require_role("owner", "moderator")),
    db: Session = Depends(get_db),
):
    return [_item_response(i) for i in InventoryRepository(db).list_low_stock()]


@router.post("/bulk-import", response_model=dict)
def bulk_import(
    file: UploadFile = File(...),
    current_user=Depends(require_role("owner", "moderator")),
    db: Session = Depends(get_db),
):
    content = file.file.read()
    return InventoryService(db).bulk_import_csv(content, current_user)


@router.get("/{item_id}", response_model=InventoryItemResponse)
def get_item(
    item_id: UUID,
    _=Depends(require_role("owner", "moderator")),
    db: Session = Depends(get_db),
):
    from app.core.exceptions import NotFoundError
    item = InventoryRepository(db).get_by_id(item_id)
    if not item or item.is_deleted:
        raise NotFoundError("InventoryItem", str(item_id))
    return _item_response(item)


@router.put("/{item_id}", response_model=InventoryItemResponse)
def update_item(
    item_id: UUID,
    payload: InventoryItemUpdate,
    current_user=Depends(require_role("owner", "moderator")),
    db: Session = Depends(get_db),
):
    return _item_response(InventoryService(db).update_item(item_id, payload, current_user))


@router.delete("/{item_id}", status_code=204)
def delete_item(
    item_id: UUID,
    current_user=Depends(require_role("owner")),
    db: Session = Depends(get_db),
):
    InventoryService(db).delete_item(item_id, current_user)


# ── Low Stock Config ──────────────────────────────────────────────────────────

@router.get("/low-stock-config", response_model=list[LowStockConfigResponse])
def list_low_stock_configs(
    _=Depends(require_role("owner")),
    db: Session = Depends(get_db),
):
    configs = db.query(__import__("app.models.inventory", fromlist=["LowStockConfig"]).LowStockConfig).all()
    result = []
    for c in configs:
        item = c.inventory_item
        result.append(LowStockConfigResponse(
            id=c.id,
            inventory_item_id=c.inventory_item_id,
            part_number=item.part_number if item else None,
            part_name=item.part_name if item else None,
            threshold=c.threshold,
            configured_by=c.configured_by,
            configured_at=c.configured_at,
        ))
    return result


@router.post("/low-stock-config", response_model=LowStockConfigResponse)
def set_low_stock_config(
    payload: LowStockConfigCreate,
    current_user=Depends(require_role("owner")),
    db: Session = Depends(get_db),
):
    svc = InventoryService(db)
    c = svc.set_low_stock_config(payload, current_user)
    item = c.inventory_item
    return LowStockConfigResponse(
        id=c.id,
        inventory_item_id=c.inventory_item_id,
        part_number=item.part_number if item else None,
        part_name=item.part_name if item else None,
        threshold=c.threshold,
        configured_by=c.configured_by,
        configured_at=c.configured_at,
    )


@router.put("/low-stock-config/{config_id}", response_model=LowStockConfigResponse)
def update_low_stock_config(
    config_id: UUID,
    payload: LowStockConfigUpdate,
    current_user=Depends(require_role("owner")),
    db: Session = Depends(get_db),
):
    svc = InventoryService(db)
    c = svc.update_low_stock_config(config_id, payload, current_user)
    item = c.inventory_item
    return LowStockConfigResponse(
        id=c.id,
        inventory_item_id=c.inventory_item_id,
        part_number=item.part_number if item else None,
        part_name=item.part_name if item else None,
        threshold=c.threshold,
        configured_by=c.configured_by,
        configured_at=c.configured_at,
    )


@router.delete("/low-stock-config/{config_id}", status_code=204)
def delete_low_stock_config(
    config_id: UUID,
    _=Depends(require_role("owner")),
    db: Session = Depends(get_db),
):
    InventoryService(db).delete_low_stock_config(config_id)
