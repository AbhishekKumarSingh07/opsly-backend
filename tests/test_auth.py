from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.conftest import auth_headers_for


def test_login_success(client: TestClient, owner_user):
    resp = client.post("/api/v1/auth/login", json={"email": "owner@test.com", "password": "testpass123"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client: TestClient, owner_user):
    resp = client.post("/api/v1/auth/login", json={"email": "owner@test.com", "password": "wrong"})
    assert resp.status_code == 401


def test_login_unknown_email(client: TestClient):
    resp = client.post("/api/v1/auth/login", json={"email": "nobody@test.com", "password": "test"})
    assert resp.status_code == 401


def test_me_authenticated(client: TestClient, owner_user):
    headers = auth_headers_for(owner_user)
    resp = client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["email"] == "owner@test.com"


def test_me_unauthenticated(client: TestClient):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_protected_route_wrong_role(client: TestClient, staff_user):
    """Staff cannot access owner-only routes."""
    headers = auth_headers_for(staff_user)
    resp = client.get("/api/v1/users/", headers=headers)
    assert resp.status_code == 403


def test_logout(client: TestClient, owner_user):
    headers = auth_headers_for(owner_user)
    resp = client.post("/api/v1/auth/logout", headers=headers)
    assert resp.status_code == 200
