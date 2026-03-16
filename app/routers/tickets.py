from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db, require_role
from app.schemas.ticket import TicketAssign, TicketCreate, TicketResponse, TicketStatusUpdate
from app.schemas.common import PaginatedResponse
from app.services.ticket_service import TicketService
from app.utils.pagination import page_offset, paginate
from app.repositories.ticket_repo import TicketRepository

router = APIRouter(prefix="/tickets", tags=["Tickets"])


@router.post("/", response_model=TicketResponse)
def create_ticket(
    payload: TicketCreate,
    x_idempotency_key: str | None = Header(default=None),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a new field service ticket.

    - Accessible by: all authenticated users.
    - Supports X-Idempotency-Key header for safe retries.
    - Returns the created ticket.
    """
    import json
    from app.utils.idempotency import check_idempotency_key, store_idempotency_key
    from app.schemas.ticket import TicketResponse

    if x_idempotency_key:
        cached = check_idempotency_key(f"ticket:{x_idempotency_key}")
        if cached:
            return TicketResponse.model_validate_json(cached)

    service = TicketService(db)
    ticket = service.create_ticket(payload, current_user)

    response_obj = TicketResponse.model_validate(ticket)
    if x_idempotency_key:
        store_idempotency_key(f"ticket:{x_idempotency_key}", response_obj.model_dump_json())

    return response_obj


@router.get("/", response_model=PaginatedResponse[TicketResponse], dependencies=[Depends(require_role("owner", "moderator"))])
def list_tickets(
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
):
    """
    List all tickets with pagination.

    - Accessible by: owner, moderator.
    - Returns a paginated list of tickets.
    """
    repo = TicketRepository(db)
    skip, limit = page_offset(page, page_size)
    items = repo.list_all(skip=skip, limit=limit)
    total = repo.count()
    return paginate(items, total, page, page_size)


@router.get("/my", response_model=list[TicketResponse])
def my_tickets(
    skip: int = 0,
    limit: int = 50,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return tickets for the current user.

    - Staff see only their assigned tickets.
    - Moderator/Owner see all tickets.
    - Accessible by: all roles.
    """
    service = TicketService(db)
    return service.get_my_tickets(current_user, skip=skip, limit=limit)


@router.get("/{ticket_id}", response_model=TicketResponse)
def get_ticket(ticket_id: UUID, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Fetch a single ticket by ID.

    - Accessible by: all authenticated users.
    """
    from app.core.exceptions import NotFoundError
    repo = TicketRepository(db)
    ticket = repo.get_by_id(ticket_id)
    if not ticket or ticket.is_deleted:
        raise NotFoundError("Ticket", str(ticket_id))
    return ticket


@router.patch("/{ticket_id}/assign", response_model=TicketResponse, dependencies=[Depends(require_role("owner", "moderator"))])
def assign_ticket(
    ticket_id: UUID,
    payload: TicketAssign,
    current_user=Depends(require_role("owner", "moderator")),
    db: Session = Depends(get_db),
):
    """
    Assign one or more technicians to a ticket (OPEN → ASSIGNED).

    - Accessible by: owner, moderator.
    """
    service = TicketService(db)
    return service.assign_ticket(ticket_id, payload.technician_ids, current_user)


@router.patch("/{ticket_id}/status", response_model=TicketResponse)
def update_ticket_status(
    ticket_id: UUID,
    payload: TicketStatusUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Transition ticket to a new status following the state machine.

    - Accessible by: all roles (role-specific transitions enforced in service layer).
    """
    service = TicketService(db)
    return service.update_status(ticket_id, payload.new_status, current_user, payload.notes)
