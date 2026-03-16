from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.core.dependencies import get_db
from app.core.security import create_access_token, hash_password
from app.models.user import User, UserRole

# ── In-memory SQLite for tests ────────────────────────────────────────────────

SQLALCHEMY_TEST_URL = "sqlite:///:memory:"

test_engine = create_engine(
    SQLALCHEMY_TEST_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function")
def test_db():
    """Create all tables, yield session, then drop all tables after test."""
    # Import all models so they register on Base.metadata
    from app.models import (  # noqa: F401
        user, site, dg_set, ticket, attendance,
        inventory, tender, expense, client, audit_log,
    )
    Base.metadata.create_all(bind=test_engine)
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def client(test_db):
    """FastAPI TestClient with overridden get_db dependency."""
    from app.main import app

    def _override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


# ── Sample fixtures ───────────────────────────────────────────────────────────

def _make_user(db, role: UserRole, email: str) -> User:
    user = User(
        name=f"Test {role.value.title()}",
        email=email,
        phone=None,
        role=role,
        hashed_password=hash_password("testpass123"),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def owner_user(test_db):
    return _make_user(test_db, UserRole.owner, "owner@test.com")


@pytest.fixture
def moderator_user(test_db):
    return _make_user(test_db, UserRole.moderator, "moderator@test.com")


@pytest.fixture
def staff_user(test_db):
    return _make_user(test_db, UserRole.staff, "staff@test.com")


def auth_headers_for(user: User) -> dict[str, str]:
    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def owner_headers(owner_user):
    return auth_headers_for(owner_user)


@pytest.fixture
def moderator_headers(moderator_user):
    return auth_headers_for(moderator_user)


@pytest.fixture
def staff_headers(staff_user):
    return auth_headers_for(staff_user)


@pytest.fixture
def sample_ticket(test_db, moderator_user):
    """A minimal open ticket created by the moderator."""
    from app.models.ticket import Ticket, TicketPriority, TicketStatus
    from datetime import datetime, timezone

    ticket = Ticket(
        reference_no="TKT-20260315-0001",
        created_by=moderator_user.id,
        status=TicketStatus.OPEN,
        priority=TicketPriority.MEDIUM,
        reported_issue="Test issue",
    )
    test_db.add(ticket)
    test_db.commit()
    test_db.refresh(ticket)
    return ticket


@pytest.fixture
def sample_inventory_item(test_db):
    """A minimal IN_STOCK inventory item."""
    from app.models.inventory import InventoryItem, InventoryItemStatus
    from decimal import Decimal

    item = InventoryItem(
        part_name="Test Part",
        part_number="TP-001",
        barcode="BARCODE123",
        unit_cost=Decimal("500.00"),
        status=InventoryItemStatus.IN_STOCK,
    )
    test_db.add(item)
    test_db.commit()
    test_db.refresh(item)
    return item
