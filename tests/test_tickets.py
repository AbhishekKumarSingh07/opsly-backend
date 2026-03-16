from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.conftest import auth_headers_for


def test_create_ticket(client: TestClient, owner_user):
    headers = auth_headers_for(owner_user)
    resp = client.post(
        "/api/v1/tickets/",
        json={"reported_issue": "DG set not starting", "priority": "HIGH"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "OPEN"
    assert data["reference_no"].startswith("TKT-")


def test_invalid_status_transition_open_to_completed(client: TestClient, owner_user, sample_ticket):
    """OPEN → COMPLETED is not a valid state machine transition."""
    headers = auth_headers_for(owner_user)
    resp = client.patch(
        f"/api/v1/tickets/{sample_ticket.id}/status",
        json={"new_status": "COMPLETED"},
        headers=headers,
    )
    assert resp.status_code == 422
    body = resp.json()
    assert "INVALID_STATUS_TRANSITION" in str(body)


def test_assign_ticket(client: TestClient, moderator_user, staff_user, sample_ticket):
    headers = auth_headers_for(moderator_user)
    resp = client.patch(
        f"/api/v1/tickets/{sample_ticket.id}/assign",
        json={"technician_ids": [str(staff_user.id)]},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ASSIGNED"


def test_close_without_after_photo_fails(client: TestClient, owner_user, test_db):
    """Completing a ticket without an AFTER photo must return 422."""
    from app.models.ticket import Ticket, TicketStatus, TicketPriority
    from app.models.user import UserRole

    ticket = Ticket(
        reference_no="TKT-20260315-0099",
        created_by=owner_user.id,
        status=TicketStatus.IN_PROGRESS,
        priority=TicketPriority.HIGH,
        reported_issue="Test close",
    )
    test_db.add(ticket)
    test_db.commit()
    test_db.refresh(ticket)

    headers = auth_headers_for(owner_user)
    resp = client.patch(
        f"/api/v1/tickets/{ticket.id}/status",
        json={"new_status": "COMPLETED"},
        headers=headers,
    )
    assert resp.status_code == 422
    assert "MISSING_AFTER_PHOTO" in str(resp.json())


def test_get_ticket_not_found(client: TestClient, owner_user):
    headers = auth_headers_for(owner_user)
    resp = client.get("/api/v1/tickets/00000000-0000-0000-0000-000000000000", headers=headers)
    assert resp.status_code == 404
