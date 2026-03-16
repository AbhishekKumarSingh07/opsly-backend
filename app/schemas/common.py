from __future__ import annotations

from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict

DataT = TypeVar("DataT")


class ErrorResponse(BaseModel):
    """Standardised error envelope returned on all error responses."""

    model_config = ConfigDict(from_attributes=True)

    status: int
    code: str
    detail: str | list


class PaginatedResponse(BaseModel, Generic[DataT]):
    """Generic paginated response wrapper."""

    model_config = ConfigDict(from_attributes=True)

    total: int
    page: int
    page_size: int
    pages: int
    items: list[DataT]


class MessageResponse(BaseModel):
    """Simple success message envelope."""

    message: str
