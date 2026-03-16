from __future__ import annotations

import io
import re
import uuid
from pathlib import Path

import boto3
from fastapi import HTTPException, UploadFile, status

from app.core.config import settings

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

# Magic bytes for allowed MIME types
_MAGIC: dict[str, bytes] = {
    "image/jpeg": b"\xff\xd8\xff",
    "image/png": b"\x89PNG",
    "image/webp": b"RIFF",
    "application/pdf": b"%PDF",
}


def _detect_mime(header: bytes) -> str | None:
    """Detect MIME type from the first 512 bytes of a file."""
    for mime, magic in _MAGIC.items():
        if header.startswith(magic):
            return mime
    return None


def _sanitize_filename(filename: str) -> str:
    """Strip path components and replace whitespace/special chars."""
    name = Path(filename).name  # remove any path traversal
    name = re.sub(r"[^\w.\-]", "_", name)  # replace unsafe characters
    return name[:200]  # cap length


def _get_s3_client():
    kwargs: dict = {
        "aws_access_key_id": settings.AWS_ACCESS_KEY_ID,
        "aws_secret_access_key": settings.AWS_SECRET_ACCESS_KEY,
        "region_name": settings.AWS_REGION,
    }
    # When S3_ENDPOINT_URL is set, point boto3 at MinIO (or any S3-compatible store)
    if settings.S3_ENDPOINT_URL:
        kwargs["endpoint_url"] = settings.S3_ENDPOINT_URL
    return boto3.client("s3", **kwargs)


async def upload_to_s3(
    file: UploadFile,
    folder: str,
    allowed_mime_types: list[str],
) -> str:
    """
    Validate and upload a file to S3.

    Validates:
    - MIME type using magic bytes (does NOT trust Content-Type header)
    - File size < 10 MB
    - Filename sanitization

    Returns:
        Full S3 URL string (https://<bucket>.s3.<region>.amazonaws.com/<key>)

    Raises:
        HTTP 422 with code INVALID_FILE on any validation failure.
    """
    # Read entire file into memory (enforce size limit)
    content = await file.read()
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"status": 422, "code": "INVALID_FILE", "detail": "File size exceeds 10 MB limit."},
        )

    # Validate magic bytes
    detected_mime = _detect_mime(content[:512])
    if detected_mime not in allowed_mime_types:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": 422,
                "code": "INVALID_FILE",
                "detail": f"Unsupported file type. Detected: {detected_mime}. Allowed: {allowed_mime_types}",
            },
        )

    safe_name = _sanitize_filename(file.filename or "upload")
    key = f"{folder}/{uuid.uuid4()}/{safe_name}"

    try:
        s3 = _get_s3_client()
        s3.upload_fileobj(
            io.BytesIO(content),
            settings.AWS_S3_BUCKET,
            key,
            ExtraArgs={"ContentType": detected_mime},
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"status": 422, "code": "INVALID_FILE", "detail": f"Upload failed: {exc}"},
        ) from exc

    # Build the public URL
    # MinIO (local dev): http://localhost:9000/<bucket>/<key>
    # AWS S3 (prod):     https://<bucket>.s3.<region>.amazonaws.com/<key>
    if settings.S3_ENDPOINT_URL:
        url = f"{settings.S3_ENDPOINT_URL.rstrip('/')}/{settings.AWS_S3_BUCKET}/{key}"
    else:
        url = f"https://{settings.AWS_S3_BUCKET}.s3.{settings.AWS_REGION}.amazonaws.com/{key}"
    return url
