from __future__ import annotations

from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException


class OpslyException(Exception):
    """Base application exception."""

    def __init__(self, status_code: int, code: str, detail: str | list) -> None:
        self.status_code = status_code
        self.code = code
        self.detail = detail


class NotFoundError(OpslyException):
    def __init__(self, resource: str, resource_id: str = "") -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            detail=f"{resource} not found" + (f": {resource_id}" if resource_id else ""),
        )


class ConflictError(OpslyException):
    def __init__(self, detail: str) -> None:
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            code="CONFLICT",
            detail=detail,
        )


class BusinessRuleError(OpslyException):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code=code,
            detail=detail,
        )


class PermissionDeniedError(OpslyException):
    def __init__(self, detail: str = "Insufficient permissions") -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            code="INSUFFICIENT_PERMISSIONS",
            detail=detail,
        )


def _error_response(status_code: int, code: str, detail: str | list) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"status": status_code, "code": code, "detail": detail},
    )


async def opsly_exception_handler(request: Request, exc: OpslyException) -> JSONResponse:
    """Handle custom OpslyException and return standardised JSON error."""
    return _error_response(exc.status_code, exc.code, exc.detail)


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Handle Starlette/FastAPI HTTP exceptions and return standardised JSON error."""
    detail = exc.detail
    if isinstance(detail, dict):
        code = detail.get("code", "HTTP_ERROR")
        msg = detail.get("detail", str(exc.detail))
    else:
        code = "HTTP_ERROR"
        msg = str(detail)
    return _error_response(exc.status_code, code, msg)


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle Pydantic V2 validation errors and return standardised JSON error."""
    errors = [
        {"field": ".".join(str(loc) for loc in err["loc"]), "message": err["msg"]}
        for err in exc.errors()
    ]
    return _error_response(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        "VALIDATION_ERROR",
        errors,
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler — logs and returns a generic 500 response."""
    import logging
    logging.getLogger("opsly").exception("Unhandled exception: %s", exc)
    return _error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "INTERNAL_SERVER_ERROR",
        "An unexpected error occurred. Please try again later.",
    )
