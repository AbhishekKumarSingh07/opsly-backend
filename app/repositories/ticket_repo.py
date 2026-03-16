from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.ticket import Ticket, TicketPhoto, TicketStatus, TicketStatusHistory, PhotoType
from app.repositories.base import BaseRepository


class TicketRepository(BaseRepository[Ticket]):
    model = Ticket

    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def get_by_reference(self, reference_no: str) -> Ticket | None:
        return (
            self.db.query(Ticket)
            .filter(Ticket.reference_no == reference_no, Ticket.is_deleted.is_(False))
            .first()
        )

    def list_for_user(self, user_id: UUID, skip: int = 0, limit: int = 50) -> list[Ticket]:
        """Return tickets where the user is a technician."""
        from app.models.ticket import ticket_technicians
        return (
            self.db.query(Ticket)
            .join(ticket_technicians, Ticket.id == ticket_technicians.c.ticket_id)
            .filter(ticket_technicians.c.user_id == user_id, Ticket.is_deleted.is_(False))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def list_by_status(self, status: TicketStatus, skip: int = 0, limit: int = 50) -> list[Ticket]:
        return (
            self.db.query(Ticket)
            .filter(Ticket.status == status, Ticket.is_deleted.is_(False))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def list_by_dg_set(self, dg_set_id: UUID) -> list[Ticket]:
        return (
            self.db.query(Ticket)
            .filter(Ticket.dg_set_id == dg_set_id, Ticket.is_deleted.is_(False))
            .all()
        )

    def get_photos_by_type(self, ticket_id: UUID, photo_type: PhotoType) -> list[TicketPhoto]:
        return (
            self.db.query(TicketPhoto)
            .filter(TicketPhoto.ticket_id == ticket_id, TicketPhoto.photo_type == photo_type)
            .all()
        )

    def add_status_history(self, history: TicketStatusHistory) -> TicketStatusHistory:
        self.db.add(history)
        self.db.flush()
        return history

    def count_open(self) -> int:
        return (
            self.db.query(Ticket)
            .filter(
                Ticket.status.in_([TicketStatus.OPEN, TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS]),
                Ticket.is_deleted.is_(False),
            )
            .count()
        )

    def list_open_for_dg_set(self, dg_set_id: UUID) -> list[Ticket]:
        """Return open/draft tickets for a specific DG set (used by AMC checker)."""
        return (
            self.db.query(Ticket)
            .filter(
                Ticket.dg_set_id == dg_set_id,
                Ticket.status.in_([TicketStatus.OPEN, TicketStatus.ASSIGNED]),
                Ticket.is_deleted.is_(False),
            )
            .all()
        )
