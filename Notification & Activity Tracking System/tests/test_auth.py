import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from app.database import engine
from app.main import app

client = TestClient(app)


def test_signup_and_login():
    response = client.post("/auth/signup", json={
        "full_name": "Admin User",
        "email": "admin@example.com",
        "password": "strongpassword",
        "role": "Admin"
    })
    assert response.status_code == 200
    result = response.json()
    assert result["email"] == "admin@example.com"

    response = client.post("/auth/login", data={
        "username": "admin@example.com",
        "password": "strongpassword"
    })
    assert response.status_code == 200
    token = response.json()["access_token"]
    assert token

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == "admin@example.com"

    response = client.post("/auth/login", data={
        "username": "admin@example.com",
        "password": "strongpassword",
        "role": "Admin"
    })
    assert response.status_code == 200
    assert response.json()["access_token"]

    response = client.post("/auth/login", data={
        "username": "admin@example.com",
        "password": "strongpassword",
        "role": "Member"
    })
    assert response.status_code == 401


def test_login_works_when_activity_log_table_is_legacy():
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS activity_logs"))
        conn.execute(text("""
            CREATE TABLE activity_logs (
                id INTEGER NOT NULL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                action VARCHAR NOT NULL,
                entity_id INTEGER NOT NULL,
                description TEXT,
                created_at DATETIME,
                is_deleted BOOLEAN NOT NULL DEFAULT 0
            )
        """))

    response = client.post("/auth/signup", json={
        "full_name": "Legacy User",
        "email": "legacy@example.com",
        "password": "strongpassword",
        "role": "Admin"
    })
    assert response.status_code == 200

    response = client.post("/auth/login", data={
        "username": "legacy@example.com",
        "password": "strongpassword",
        "role": "Admin"
    })
    assert response.status_code == 200
    assert response.json()["access_token"]


def test_activities_endpoints_work_with_legacy_activity_logs_table():
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS activity_logs"))
        conn.execute(text("""
            CREATE TABLE activity_logs (
                id INTEGER NOT NULL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                action VARCHAR NOT NULL,
                entity_id INTEGER NOT NULL,
                description TEXT,
                created_at DATETIME,
                is_deleted BOOLEAN NOT NULL DEFAULT 0
            )
        """))

    signup_response = client.post("/auth/signup", json={
        "full_name": "Activity Admin",
        "email": "activity@example.com",
        "password": "strongpassword",
        "role": "Admin"
    })
    assert signup_response.status_code == 200

    login_response = client.post("/auth/login", data={
        "username": "activity@example.com",
        "password": "strongpassword",
        "role": "Admin"
    })
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    activities_response = client.get("/activities/", headers={"Authorization": f"Bearer {token}"})
    assert activities_response.status_code == 200


def test_activities_include_performing_user_details():
    signup_response = client.post("/auth/signup", json={
        "full_name": "Actor User",
        "email": "actor@example.com",
        "password": "strongpassword",
        "role": "Admin"
    })
    assert signup_response.status_code == 200
    user_id = signup_response.json()["id"]

    login_response = client.post("/auth/login", data={
        "username": "actor@example.com",
        "password": "strongpassword",
        "role": "Admin"
    })
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    activities_response = client.get("/activities/", headers={"Authorization": f"Bearer {token}"})
    assert activities_response.status_code == 200

    activities = activities_response.json()
    matching_activity = next((activity for activity in activities if activity["user_id"] == user_id), None)
    assert matching_activity is not None
    assert matching_activity["performed_by"]["full_name"] == "Actor User"


def test_login_returns_simple_access_token():
    signup_response = client.post("/auth/signup", json={
        "full_name": "Simple Login User",
        "email": "simple-login@example.com",
        "password": "strongpassword",
        "role": "Admin"
    })
    assert signup_response.status_code == 200

    login_response = client.post("/auth/login", data={
        "username": "simple-login@example.com",
        "password": "strongpassword",
        "role": "Admin"
    })
    assert login_response.status_code == 200
    payload = login_response.json()
    assert payload["access_token"]
    assert payload["token_type"] == "bearer"
    assert "refresh_token" not in payload


def test_get_project_activities_returns_200_for_project_member():
    signup_response = client.post("/auth/signup", json={
        "full_name": "Project Owner",
        "email": "owner@example.com",
        "password": "strongpassword",
        "role": "Admin"
    })
    assert signup_response.status_code == 200

    login_response = client.post("/auth/login", data={
        "username": "owner@example.com",
        "password": "strongpassword",
        "role": "Admin"
    })
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    project_response = client.post(
        "/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Alpha", "description": "sample"},
    )
    assert project_response.status_code in {200, 201}
    project_id = project_response.json()["id"]

    activities_response = client.get(
        f"/activities/project/{project_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert activities_response.status_code == 200
    assert isinstance(activities_response.json(), list)
