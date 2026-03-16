from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.tender import Tender, TenderMilestone, TenderDocument, TenderStatus
from app.repositories.base import BaseRepository


class TenderRepository(BaseRepository[Tender]):
    model = Tender

    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def get_by_reference(self, reference_no: str) -> Tender | None:
        return (
            self.db.query(Tender)
            .filter(Tender.reference_no == reference_no, Tender.is_deleted.is_(False))
            .first()
        )

    def list_by_status(self, status: TenderStatus, skip: int = 0, limit: int = 50) -> list[Tender]:
        return (
            self.db.query(Tender)
            .filter(Tender.status == status, Tender.is_deleted.is_(False))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_by_status(self) -> dict[str, int]:
        from sqlalchemy import func
        rows = (
            self.db.query(Tender.status, func.count(Tender.id))
            .filter(Tender.is_deleted.is_(False))
            .group_by(Tender.status)
            .all()
        )
        return {str(row[0].value): row[1] for row in rows}

    def get_milestone(self, milestone_id: UUID) -> TenderMilestone | None:
        return self.db.get(TenderMilestone, milestone_id)

    def add_milestone(self, milestone: TenderMilestone) -> TenderMilestone:
        self.db.add(milestone)
        self.db.flush()
        self.db.refresh(milestone)
        return milestone

    def add_document(self, doc: TenderDocument) -> TenderDocument:
        self.db.add(doc)
        self.db.flush()
        self.db.refresh(doc)
        return doc
