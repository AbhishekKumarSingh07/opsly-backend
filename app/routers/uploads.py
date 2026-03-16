from __future__ import annotations

from fastapi import APIRouter, Depends, File, Header, UploadFile
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db, require_role
from app.utils.file_upload import upload_to_s3
from app.utils.idempotency import check_idempotency_key, store_idempotency_key

router = APIRouter(prefix="/uploads", tags=["Uploads"])


@router.post("/photo")
async def upload_photo(
    file: UploadFile = File(...),
    x_idempotency_key: str | None = Header(default=None),
    current_user=Depends(get_current_user),
):
    """
    Upload an image (JPEG, PNG, WebP).

    - Validates MIME type via magic bytes.
    - File size limit: 10 MB.
    - Supports X-Idempotency-Key.
    - Accessible by: all authenticated users.
    - Returns: { url, key }
    """
    if x_idempotency_key:
        cached = check_idempotency_key(f"photo:{x_idempotency_key}")
        if cached:
            import json
            return json.loads(cached)

    url = await upload_to_s3(file, "photos", ["image/jpeg", "image/png", "image/webp"])
    key = url.split(".amazonaws.com/", 1)[-1] if ".amazonaws.com/" in url else url
    result = {"url": url, "key": key}

    if x_idempotency_key:
        import json
        store_idempotency_key(f"photo:{x_idempotency_key}", json.dumps(result))

    return result


@router.post("/document", dependencies=[Depends(require_role("owner", "moderator"))])
async def upload_document(
    file: UploadFile = File(...),
    x_idempotency_key: str | None = Header(default=None),
    current_user=Depends(require_role("owner", "moderator")),
):
    """
    Upload a PDF document.

    - Validates MIME type via magic bytes.
    - File size limit: 10 MB.
    - Supports X-Idempotency-Key.
    - Accessible by: owner, moderator.
    - Returns: { url, key }
    """
    if x_idempotency_key:
        cached = check_idempotency_key(f"doc:{x_idempotency_key}")
        if cached:
            import json
            return json.loads(cached)

    url = await upload_to_s3(file, "documents", ["application/pdf"])
    key = url.split(".amazonaws.com/", 1)[-1] if ".amazonaws.com/" in url else url
    result = {"url": url, "key": key}

    if x_idempotency_key:
        import json
        store_idempotency_key(f"doc:{x_idempotency_key}", json.dumps(result))

    return result
