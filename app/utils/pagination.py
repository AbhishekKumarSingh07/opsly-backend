from __future__ import annotations

import math
from typing import TypeVar

from app.schemas.common import PaginatedResponse

T = TypeVar("T")


def paginate(items: list[T], total: int, page: int, page_size: int) -> PaginatedResponse[T]:
    """
    Wrap a list of items into a PaginatedResponse envelope.

    Args:
        items: The records for the current page.
        total: Total matching records (across all pages).
        page: Current 1-based page number.
        page_size: Number of records per page.
    """
    pages = math.ceil(total / page_size) if page_size > 0 else 0
    return PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
        items=items,
    )


def page_offset(page: int, page_size: int) -> tuple[int, int]:
    """Return (skip, limit) tuple for SQLAlchemy queries from 1-based page/page_size."""
    skip = (page - 1) * page_size
    return skip, page_size
