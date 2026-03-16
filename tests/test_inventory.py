from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.conftest import auth_headers_for


def test_intake_part_success(client: TestClient, moderator_user):
    headers = auth_headers_for(moderator_user)
    resp = client.post(
        "/api/v1/inventory/intake",
        json={
            "part_name": "Coolant Filter",
            "part_number": "CF-100",
            "barcode": "BCODE-0001",
            "unit_cost": "250.00",
        },
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "IN_STOCK"
    assert data["barcode"] == "BCODE-0001"


def test_intake_duplicate_barcode_rejected(client: TestClient, moderator_user, sample_inventory_item):
    headers = auth_headers_for(moderator_user)
    resp = client.post(
        "/api/v1/inventory/intake",
        json={
            "part_name": "Duplicate Part",
            "part_number": "DP-001",
            "barcode": "BARCODE123",  # already exists in sample_inventory_item
            "unit_cost": "100.00",
        },
        headers=headers,
    )
    assert resp.status_code == 409


def test_checkout_by_staff_fails(client: TestClient, staff_user, sample_inventory_item, sample_ticket):
    """Staff cannot check out parts — only moderator/owner."""
    headers = auth_headers_for(staff_user)
    resp = client.post(
        "/api/v1/inventory/checkout",
        json={"item_id": str(sample_inventory_item.id), "ticket_id": str(sample_ticket.id)},
        headers=headers,
    )
    assert resp.status_code == 403


def test_checkout_and_return_reconciles(client: TestClient, moderator_user, sample_inventory_item, sample_ticket, test_db):
    """Full checkout → install → return cycle reconciles correctly."""
    from app.models.ticket import TicketStatus
    sample_ticket.status = TicketStatus.IN_PROGRESS
    test_db.commit()

    headers = auth_headers_for(moderator_user)

    # Checkout
    resp = client.post(
        "/api/v1/inventory/checkout",
        json={"item_id": str(sample_inventory_item.id), "ticket_id": str(sample_ticket.id)},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "CHECKED_OUT"

    # Return scan
    resp2 = client.post(
        "/api/v1/inventory/return",
        json={"barcode": "BARCODE123"},
        headers=headers,
    )
    # Should fail because item is CHECKED_OUT, not PENDING_RETURN
    assert resp2.status_code == 422
    assert "PENDING_RETURN" in str(resp2.json())


def test_return_unknown_barcode(client: TestClient, moderator_user):
    headers = auth_headers_for(moderator_user)
    resp = client.post(
        "/api/v1/inventory/return",
        json={"barcode": "NOSUCHBARCODE"},
        headers=headers,
    )
    assert resp.status_code == 404
