"""Tests for general REST API endpoints and error paths."""


def test_health_check(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "community-service-desk"
    assert data["database"] == "connected"


def test_dashboard_stats_endpoint(client, auth_agent_a):
    response = client.get("/api/v1/tickets/stats/dashboard", headers=auth_agent_a)
    assert response.status_code == 200
    data = response.json()
    assert "new_count" in data
    assert "open_count" in data
    assert "total_tickets" in data


def test_queue_endpoints(client, auth_admin_a, auth_agent_a):
    # 1. Admin creates queue
    create_resp = client.post(
        "/api/v1/queues",
        json={"name": "Facilities & Grounds", "description": "Building maintenance"},
        headers=auth_admin_a,
    )
    assert create_resp.status_code == 201
    q_data = create_resp.json()
    assert q_data["name"] == "Facilities & Grounds"

    # 2. Agent lists queues
    list_resp = client.get("/api/v1/queues", headers=auth_agent_a)
    assert list_resp.status_code == 200
    names = [q["name"] for q in list_resp.json()]
    assert "Facilities & Grounds" in names


def test_admin_member_management(client, auth_admin_a, auth_agent_a):
    # Non-admin cannot access admin endpoint
    denied_resp = client.get("/api/v1/admin/members", headers=auth_agent_a)
    assert denied_resp.status_code == 403

    # Admin lists members
    list_resp = client.get("/api/v1/admin/members", headers=auth_admin_a)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 1

    # Admin adds member
    add_resp = client.post(
        "/api/v1/admin/members",
        json={
            "email": "new_volunteer@alpha.org",
            "display_name": "New Volunteer",
            "password": "SecurePassword123!",
            "role": "agent",
        },
        headers=auth_admin_a,
    )
    assert add_resp.status_code == 201
    assert add_resp.json()["role"] == "agent"
