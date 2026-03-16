from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError, PermissionDeniedError
from app.models.inventory import InventoryItem, InventoryItemStatus, InventoryMovement
from app.models.ticket import PhotoType, TicketPhoto, TicketStatus
from app.models.user import User, UserRole
from app.repositories.inventory_repo import InventoryRepository
from app.repositories.ticket_repo import TicketRepository
from app.schemas.inventory import InventoryIntakeSchema


class InventoryService:
    """Business logic for serialized inventory lifecycle management."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = InventoryRepository(db)

    def intake_part(self, payload: InventoryIntakeSchema, actor: User) -> InventoryItem:
        """
        Receive a new part into inventory.
        Validates barcode uniqueness, creates IN_STOCK record and movement log.
        """
        if payload.barcode:
            existing = self.repo.get_by_barcode(payload.barcode)
            if existing:
                raise ConflictError(f"Barcode '{payload.barcode}' already exists in inventory.")

        if payload.serial_no:
            existing_serial = self.repo.get_by_serial(payload.serial_no)
            if existing_serial:
                raise ConflictError(f"Serial number '{payload.serial_no}' already exists.")

        item = InventoryItem(
            part_name=payload.part_name,
            part_number=payload.part_number,
            serial_no=payload.serial_no,
            barcode=payload.barcode,
            description=payload.description,
            unit_cost=payload.unit_cost,
            status=InventoryItemStatus.IN_STOCK,
        )
        self.repo.create(item)
        self._record_movement(item, None, InventoryItemStatus.IN_STOCK, actor, None, "Intake")
        return item

    def checkout_part(self, item_id: UUID, ticket_id: UUID, actor: User) -> InventoryItem:
        """
        Check out a part to a ticket.
        Only moderator/owner can perform checkouts — staff cannot self-checkout.
        """
        if actor.role == UserRole.staff:
            raise PermissionDeniedError("Staff cannot check out parts. Request a moderator.")

        item = self.repo.get_by_id(item_id)
        if not item or item.is_deleted:
            raise NotFoundError("InventoryItem", str(item_id))

        if item.status != InventoryItemStatus.IN_STOCK:
            raise BusinessRuleError(
                "ITEM_NOT_IN_STOCK",
                f"Item is currently {item.status.value}, not IN_STOCK.",
            )

        ticket_repo = TicketRepository(self.db)
        ticket = ticket_repo.get_by_id(ticket_id)
        if not ticket:
            raise NotFoundError("Ticket", str(ticket_id))

        if ticket.status not in (TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS):
            raise BusinessRuleError(
                "INVALID_TICKET_STATUS",
                f"Parts can only be checked out for ASSIGNED or IN_PROGRESS tickets. "
                f"Ticket is currently {ticket.status.value}.",
            )

        item.status = InventoryItemStatus.CHECKED_OUT
        item.current_ticket_id = ticket_id
        item.checked_out_at = datetime.now(timezone.utc)
        item.checked_out_by = actor.id

        self.repo.save(item)
        self._record_movement(item, InventoryItemStatus.IN_STOCK, InventoryItemStatus.CHECKED_OUT, actor, ticket_id)
        return item

    def record_installation(
        self,
        item_id: UUID,
        ticket_id: UUID,
        actor: User,
        part_new_photo_url: str,
        part_old_photo_url: str,
    ) -> InventoryItem:
        """
        Record that a part has been installed on a ticket.
        Saves both PART_NEW and PART_OLD photos.
        Transitions item to PENDING_RETURN.
        """
        item = self.repo.get_by_id(item_id)
        if not item or item.is_deleted:
            raise NotFoundError("InventoryItem", str(item_id))

        if item.status != InventoryItemStatus.CHECKED_OUT or item.current_ticket_id != ticket_id:
            raise BusinessRuleError(
                "ITEM_NOT_ON_TICKET",
                "Item is not checked out on this ticket.",
            )

        # Save photos
        for photo_type, url in [
            (PhotoType.PART_NEW, part_new_photo_url),
            (PhotoType.PART_OLD, part_old_photo_url),
        ]:
            photo = TicketPhoto(
                ticket_id=ticket_id,
                photo_type=photo_type,
                s3_url=url,
                uploaded_by=actor.id,
                uploaded_at=datetime.now(timezone.utc),
            )
            self.db.add(photo)

        item.status = InventoryItemStatus.PENDING_RETURN
        self.repo.save(item)
        self._record_movement(
            item, InventoryItemStatus.CHECKED_OUT, InventoryItemStatus.PENDING_RETURN, actor, ticket_id, "Installed"
        )
        return item

    def receive_returned_part(self, scanned_barcode: str, actor: User, notes: str | None = None) -> InventoryItem:
        """
        Process a returned part by barcode scan.
        Only moderator/owner can receive returns.
        """
        if actor.role == UserRole.staff:
            raise PermissionDeniedError("Staff cannot receive returned parts.")

        item = self.repo.get_by_barcode(scanned_barcode)
        if not item:
            raise NotFoundError("InventoryItem", f"barcode={scanned_barcode}")

        if item.status != InventoryItemStatus.PENDING_RETURN:
            raise BusinessRuleError(
                "ITEM_NOT_PENDING_RETURN",
                f"Item status is {item.status.value}, expected PENDING_RETURN.",
            )

        ticket_id = item.current_ticket_id
        item.status = InventoryItemStatus.CONSUMED
        item.returned_at = datetime.now(timezone.utc)
        item.received_by = actor.id
        self.repo.save(item)
        self._record_movement(
            item, InventoryItemStatus.PENDING_RETURN, InventoryItemStatus.CONSUMED, actor, ticket_id, notes
        )

        # Check if all parts for the parent ticket are reconciled
        if ticket_id:
            remaining = self.repo.list_checked_out_for_ticket(ticket_id)
            if not remaining:
                from app.services.notification_service import NotificationService
                NotificationService(self.db).notify_parts_dispatched(str(ticket_id))

        return item

    def _record_movement(
        self,
        item: InventoryItem,
        from_status: InventoryItemStatus | None,
        to_status: InventoryItemStatus,
        actor: User,
        ticket_id: UUID | None,
        notes: str | None = None,
    ) -> None:
        movement = InventoryMovement(
            item_id=item.id,
            from_status=from_status.value if from_status else None,
            to_status=to_status.value,
            ticket_id=ticket_id,
            actor_id=actor.id,
            notes=notes,
            timestamp=datetime.now(timezone.utc),
        )
        self.repo.add_movement(movement)
