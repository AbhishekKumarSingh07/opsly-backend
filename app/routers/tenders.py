from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db, require_role
from app.repositories.tender_repo import TenderRepository
from app.schemas.tender import (
    MilestoneCreate,
    MilestoneUpdate,
    TenderCreate,
    TenderDocumentResponse,
    TenderMilestoneResponse,
    TenderResponse,
    TenderStatusUpdate,
)
from app.schemas.common import PaginatedResponse
from app.services.tender_service import TenderService
from app.utils.file_upload import upload_to_s3
from app.utils.pagination import page_offset, paginate

router = APIRouter(prefix="/tenders", tags=["Tenders"])


@router.post("/", response_model=TenderResponse, dependencies=[Depends(require_role("owner", "moderator"))])
def create_tender(
    payload: TenderCreate,
    x_idempotency_key: str | None = Header(default=None),
    current_user=Depends(require_role("owner", "moderator")),
    db: Session = Depends(get_db),
):
    """
    Create a new tender in BIDDING status.

    - Accessible by: owner, moderator.
    - Supports X-Idempotency-Key.
    """
    from app.utils.idempotency import check_idempotency_key, store_idempotency_key

    if x_idempotency_key:
        cached = check_idempotency_key(f"tender:{x_idempotency_key}")
        if cached:
            return TenderResponse.model_validate_json(cached)

    service = TenderService(db)
    tender = service.create_tender(payload, current_user)
    response_obj = TenderResponse.model_validate(tender)

    if x_idempotency_key:
        store_idempotency_key(f"tender:{x_idempotency_key}", response_obj.model_dump_json())

    return response_obj


@router.get("/", response_model=PaginatedResponse[TenderResponse], dependencies=[Depends(require_role("owner", "moderator"))])
def list_tenders(
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
):
    """
    List all tenders with pagination.

    - Accessible by: owner, moderator.
    """
    repo = TenderRepository(db)
    skip, limit = page_offset(page, page_size)
    items = repo.list_all(skip=skip, limit=limit)
    total = repo.count()
    return paginate(items, total, page, page_size)


@router.get("/{tender_id}", response_model=TenderResponse, dependencies=[Depends(require_role("owner", "moderator"))])
def get_tender(tender_id: UUID, db: Session = Depends(get_db)):
    """
    Fetch a single tender by ID.

    - Accessible by: owner, moderator.
    """
    from app.core.exceptions import NotFoundError
    repo = TenderRepository(db)
    tender = repo.get_by_id(tender_id)
    if not tender or tender.is_deleted:
        raise NotFoundError("Tender", str(tender_id))
    return tender


@router.patch("/{tender_id}/status", response_model=TenderResponse)
def update_tender_status(
    tender_id: UUID,
    payload: TenderStatusUpdate,
    current_user=Depends(require_role("owner", "moderator")),
    db: Session = Depends(get_db),
):
    """
    Transition a tender to a new status.

    - Validates state machine transitions.
    - Accessible by: owner, moderator.
    """
    service = TenderService(db)
    return service.update_status(tender_id, payload, current_user)


@router.post("/{tender_id}/milestones", response_model=TenderMilestoneResponse)
def add_milestone(
    tender_id: UUID,
    payload: MilestoneCreate,
    current_user=Depends(require_role("owner", "moderator")),
    db: Session = Depends(get_db),
):
    """
    Add a payment milestone to a tender.

    - Accessible by: owner, moderator.
    """
    service = TenderService(db)
    return service.add_milestone(tender_id, payload, current_user)


@router.patch("/{tender_id}/milestones/{milestone_id}", response_model=TenderMilestoneResponse)
def update_milestone(
    tender_id: UUID,
    milestone_id: UUID,
    payload: MilestoneUpdate,
    current_user=Depends(require_role("owner", "moderator")),
    db: Session = Depends(get_db),
):
    """
    Update a tender milestone (completion date, payment status).

    - Accessible by: owner, moderator.
    """
    service = TenderService(db)
    return service.update_milestone(milestone_id, payload, current_user)


@router.post("/{tender_id}/documents", response_model=TenderDocumentResponse)
async def upload_tender_document(
    tender_id: UUID,
    document_type: str = Form(...),
    file: UploadFile = File(...),
    current_user=Depends(require_role("owner", "moderator")),
    db: Session = Depends(get_db),
):
    """
    Upload a document (PDF) to a tender.

    - Validates MIME type via magic bytes.
    - Accessible by: owner, moderator.
    """
    s3_url = await upload_to_s3(file, f"tenders/{tender_id}", ["application/pdf"])
    service = TenderService(db)
    return service.attach_document(tender_id, document_type, file.filename or "document.pdf", s3_url, current_user)


@router.get("/{tender_id}/documents", response_model=list[TenderDocumentResponse], dependencies=[Depends(require_role("owner", "moderator"))])
def list_tender_documents(tender_id: UUID, db: Session = Depends(get_db)):
    """
    List all documents attached to a tender.

    - Accessible by: owner, moderator.
    """
    from app.core.exceptions import NotFoundError
    repo = TenderRepository(db)
    tender = repo.get_by_id(tender_id)
    if not tender:
        raise NotFoundError("Tender", str(tender_id))
    return tender.documents
