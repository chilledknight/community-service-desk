"""Tests for Authentication."""

from community_service_desk.models.user import User
from community_service_desk.services.auth_service import AuthService


def test_valid_login(client, user_admin_a, org_alpha):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": user_admin_a.email,
            "password": "Password123!",
            "organization_slug": org_alpha.slug,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["email"] == user_admin_a.email
    assert data["role"] == "organization_admin"
    assert data["organization_id"] == org_alpha.id


def test_invalid_login_wrong_password(client, user_admin_a):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": user_admin_a.email, "password": "WrongPassword!"},
    )
    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]


def test_invalid_login_nonexistent_user(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.org", "password": "Password123!"},
    )
    assert response.status_code == 401


def test_inactive_user_cannot_login(client, db, org_alpha):
    inactive = User(
        email="inactive@alpha.org",
        display_name="Inactive User",
        password_hash=AuthService.hash_password("Password123!"),
        active=False,
    )
    db.add(inactive)
    db.commit()

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "inactive@alpha.org", "password": "Password123!"},
    )
    assert response.status_code == 401


def test_get_me_endpoint(client, auth_agent_a, user_agent_a):
    response = client.get("/api/v1/auth/me", headers=auth_agent_a)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == user_agent_a.email
    assert data["display_name"] == user_agent_a.display_name
