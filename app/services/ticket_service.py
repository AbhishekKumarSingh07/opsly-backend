from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, NotFoundError, PermissionDeniedError
from app.models.ticket import (
    PhotoType,
    Ticket,
    TicketPhoto,
    TicketPriority,
    TicketStatus,
    TicketStatusHistory,
)
from app.models.user import User, UserRole
from app.repositories.inventory_repo import InventoryRepository
from app.repositories.ticket_repo import TicketRepository
from app.schemas.ticket import TicketCreate

# ─── State machine ────────────────────────────────────────────────────────────

VALID_TRANSITIONS: dict[TicketStatus, list[TicketStatus]] = {
    TicketStatus.OPEN: [TicketStatus.ASSIGNED, TicketStatus.CANCELLED],
    TicketStatus.ASSIGNED: [TicketStatus.EN_ROUTE, TicketStatus.CANCELLED],
    TicketStatus.EN_ROUTE: [TicketStatus.IN_PROGRESS, TicketStatus.CANCELLED],
    TicketStatus.IN_PROGRESS: [
        TicketStatus.WAITING_FOR_PARTS,
        TicketStatus.COMPLETED,
        TicketStatus.CANCELLED,
    ],
    TicketStatus.WAITING_FOR_PARTS: [TicketStatus.IN_PROGRESS, TicketStatus.CANCELLED],
    TicketStatus.COMPLETED: [TicketStatus.INVOICED, TicketStatus.CLOSED, TicketStatus.CANCELLED],
    TicketStatus.INVOICED: [TicketStatus.CLOSED],
    TicketStatus.CANCELLED: [],
}

# Statuses reachable only by moderator/owner
MODERATOR_ONLY_TRANSITIONS: set[TicketStatus] = {
    TicketStatus.ASSIGNED,
    TicketStatus.INVOICED,
    TicketStatus.CLOSED,
    TicketStatus.CANCELLED,
}

_REFERENCE_RE = re.compile(r"^TKT-\d{8}-\d{4}$")


def _generate_reference(db: Session) -> str:
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    prefix = f"TKT-{date_str}-"
    # Count today's tickets to build sequence
    from sqlalchemy import func
    from app.db.base import Base

    count = (
        db.query(func.count(Ticket.id))
        .filter(Ticket.reference_no.like(f"{prefix}%"))
        .scalar()
        or 0
    )
    return f"{prefix}{(count + 1):04d}"


class TicketService:
    """Ticket lifecycle management with strict state machine enforcement."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = TicketRepository(db)
        self.inv_repo = InventoryRepository(db)

    def create_ticket(self, payload: TicketCreate, created_by: User) -> Ticket:
        """Create a new ticket in OPEN status."""
        ticket = Ticket(
            reference_no=_generate_reference(self.db),
            dg_set_id=payload.dg_set_id,
            created_by=created_by.id,
            status=TicketStatus.OPEN,
            priority=payload.priority,
            reported_issue=payload.reported_issue,
            notes=payload.notes,
        )
        result = self.repo.create(ticket)
        self._record_history(result, None, TicketStatus.OPEN, created_by, "Ticket created")
        return result

    def assign_ticket(self, ticket_id: UUID, technician_ids: list[UUID], moderator: User) -> Ticket:
        """Assign one or more technicians and transition OPEN → ASSIGNED."""
        ticket = self._get_or_raise(ticket_id)
        self._validate_transition(ticket, TicketStatus.ASSIGNED, moderator)

        from app.repositories.user_repo import UserRepository
        user_repo = UserRepository(self.db)
        technicians = [user_repo.get_by_id(tid) for tid in technician_ids]
        technicians = [t for t in technicians if t]

        ticket.technicians = technicians
        ticket.status = TicketStatus.ASSIGNED
        result = self.repo.save(ticket)
        self._record_history(result, TicketStatus.OPEN, TicketStatus.ASSIGNED, moderator, "Assigned to technicians")
        return result

    def update_status(
        self, ticket_id: UUID, new_status: TicketStatus, user: User, notes: str | None = None
    ) -> Ticket:
        """
        Transition ticket to a new status, enforcing the state machine.
        Raises HTTP 422 on invalid transitions or failed completion validation.
        """
        ticket = self._get_or_raise(ticket_id)
        old_status = ticket.status
        self._validate_transition(ticket, new_status, user)

        if new_status == TicketStatus.COMPLETED:
            self._validate_completion(ticket, user)

        if new_status == TicketStatus.COMPLETED:
            ticket.completed_at = datetime.now(timezone.utc)
        if new_status == TicketStatus.INVOICED:
            ticket.invoiced_at = datetime.now(timezone.utc)
        if new_status == TicketStatus.CANCELLED:
            self.repo.soft_delete(ticket, deleted_by=user.id)

        ticket.status = new_status
        result = self.repo.save(ticket)
        self._record_history(result, old_status, new_status, user, notes)
        return result

    def add_photo(
        self,
        ticket_id: UUID,
        photo_type: PhotoType,
        s3_url: str,
        uploader: User,
        gps_lat: float | None = None,
        gps_lng: float | None = None,
    ) -> TicketPhoto:
        """Attach a photo to a ticket."""
        ticket = self._get_or_raise(ticket_id)
        photo = TicketPhoto(
            ticket_id=ticket.id,
            photo_type=photo_type,
            s3_url=s3_url,
            gps_lat=gps_lat,
            gps_lng=gps_lng,
            uploaded_by=uploader.id,
            uploaded_at=datetime.now(timezone.utc),
        )
        self.db.add(photo)
        self.db.flush()
        self.db.refresh(photo)
        return photo

    def get_my_tickets(self, user: User, skip: int = 0, limit: int = 50) -> list[Ticket]:
        """Staff see only their assigned tickets; moderators/owners see all."""
        if user.role == UserRole.staff:
            return self.repo.list_for_user(user.id, skip=skip, limit=limit)
        return self.repo.list_all(skip=skip, limit=limit)

    # ─── Private helpers ──────────────────────────────────────────────────────

    def _get_or_raise(self, ticket_id: UUID) -> Ticket:
        ticket = self.repo.get_by_id(ticket_id)
        if not ticket or ticket.is_deleted:
            raise NotFoundError("Ticket", str(ticket_id))
        return ticket

    def _validate_transition(self, ticket: Ticket, new_status: TicketStatus, user: User) -> None:
        allowed = VALID_TRANSITIONS.get(ticket.status, [])
        if new_status not in allowed:
            raise BusinessRuleError(
                "INVALID_STATUS_TRANSITION",
                f"Cannot transition from {ticket.status.value} to {new_status.value}.",
            )
        if new_status in MODERATOR_ONLY_TRANSITIONS and user.role == UserRole.staff:
            raise PermissionDeniedError(
                f"Only moderator/owner can set status to {new_status.value}."
            )

    def _validate_completion(self, ticket: Ticket, user: User) -> None:
        """Enforce completion requirements before marking a ticket COMPLETED.
        Owners and moderators can bypass photo requirements."""
        # Owners/moderators can force-complete without photo requirements
        if user.role in (UserRole.owner, UserRole.moderator):
            return

        after_photos = self.repo.get_photos_by_type(ticket.id, PhotoType.AFTER)
        if not after_photos:
            raise BusinessRuleError(
                "MISSING_AFTER_PHOTO",
                "At least one AFTER photo is required to complete a ticket.",
            )

        checked_out = self.inv_repo.list_checked_out_for_ticket(ticket.id)
        for item in checked_out:
            part_new = self.repo.get_photos_by_type(ticket.id, PhotoType.PART_NEW)
            part_old = self.repo.get_photos_by_type(ticket.id, PhotoType.PART_OLD)
            if not part_new or not part_old:
                raise BusinessRuleError(
                    "MISSING_PART_PHOTOS",
                    f"Part {item.part_number} (barcode: {item.barcode}) requires "
                    "PART_NEW and PART_OLD photos before ticket can be completed.",
                )

    def _record_history(
        self,
        ticket: Ticket,
        from_status: TicketStatus | None,
        to_status: TicketStatus,
        user: User,
        notes: str | None,
    ) -> None:
        history = TicketStatusHistory(
            ticket_id=ticket.id,
            from_status=from_status.value if from_status else None,
            to_status=to_status.value,
            changed_by=user.id,
            changed_at=datetime.now(timezone.utc),
            notes=notes,
        )
        self.repo.add_status_history(history)
