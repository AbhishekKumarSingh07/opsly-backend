from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.bulk_import import BulkImportLog, ImportType
from app.repositories.base import BaseRepository


class BulkImportRepository(BaseRepository[BulkImportLog]):
    model = BulkImportLog

    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def list_by_actor(self, actor_id: UUID, skip: int = 0, limit: int = 50) -> list[BulkImportLog]:
        return (
            self.db.query(BulkImportLog)
            .filter(BulkImportLog.imported_by == actor_id)
            .order_by(BulkImportLog.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def list_all_ordered(self, skip: int = 0, limit: int = 100) -> list[BulkImportLog]:
        return (
            self.db.query(BulkImportLog)
            .order_by(BulkImportLog.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
