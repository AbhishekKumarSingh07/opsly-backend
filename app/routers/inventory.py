from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db, require_role
from app.repositories.inventory_repo import InventoryRepository
from app.schemas.common import PaginatedResponse
from app.schemas.inventory import (
    InventoryCheckoutSchema,
    InventoryIntakeSchema,
    InventoryItemResponse,
    InventoryReturnSchema,
)
from app.services.inventory_service import InventoryService
from app.utils.pagination import paginate

router = APIRouter(prefix="/inventory", tags=["Inventory"])


@router.post("/intake", response_model=InventoryItemResponse, dependencies=[Depends(require_role("owner", "moderator"))])
def intake_part(
    payload: InventoryIntakeSchema,
    x_idempotency_key: str | None = Header(default=None),
    current_user=Depends(require_role("owner", "moderator")),
    db: Session = Depends(get_db),
):
    """
    Receive a new serialized part into inventory.

    - Validates barcode uniqueness.
    - Accessible by: owner, moderator.
    - Supports X-Idempotency-Key.
    """
    from app.utils.idempotency import check_idempotency_key, store_idempotency_key

    if x_idempotency_key:
        cached = check_idempotency_key(f"inventory_intake:{x_idempotency_key}")
        if cached:
            return InventoryItemResponse.model_validate_json(cached)

    service = InventoryService(db)
    item = service.intake_part(payload, current_user)
    response_obj = InventoryItemResponse.model_validate(item)

    if x_idempotency_key:
        store_idempotency_key(f"inventory_intake:{x_idempotency_key}", response_obj.model_dump_json())

    return response_obj


@router.post("/checkout", response_model=InventoryItemResponse)
def checkout_part(
    payload: InventoryCheckoutSchema,
    current_user=Depends(require_role("owner", "moderator")),
    db: Session = Depends(get_db),
):
    """
    Check out a part to a ticket.

    - Staff CANNOT self-checkout.
    - Accessible by: owner, moderator.
    """
    service = InventoryService(db)
    return service.checkout_part(payload.item_id, payload.ticket_id, current_user)


@router.post("/return", response_model=InventoryItemResponse)
def receive_return(
    payload: InventoryReturnSchema,
    current_user=Depends(require_role("owner", "moderator")),
    db: Session = Depends(get_db),
):
    """
    Process a returned part by barcode scan.

    - Sets item status to CONSUMED.
    - Accessible by: owner, moderator.
    """
    service = InventoryService(db)
    return service.receive_returned_part(payload.barcode, current_user, payload.notes)


@router.get("/", response_model=PaginatedResponse[InventoryItemResponse], dependencies=[Depends(require_role("owner", "moderator"))])
def list_inventory(
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
):
    """
    List all inventory items (paginated).

    - Accessible by: owner, moderator.
    """
    repo = InventoryRepository(db)
    skip = (page - 1) * page_size
    items = repo.list_all(skip=skip, limit=page_size)
    total = repo.count()
    return paginate(
        [InventoryItemResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{item_id}", response_model=InventoryItemResponse, dependencies=[Depends(require_role("owner", "moderator"))])
def get_item(item_id: UUID, db: Session = Depends(get_db)):
    """
    Fetch a single inventory item by ID.

    - Accessible by: owner, moderator.
    """
    from app.core.exceptions import NotFoundError
    repo = InventoryRepository(db)
    item = repo.get_by_id(item_id)
    if not item or item.is_deleted:
        raise NotFoundError("InventoryItem", str(item_id))
    return item
