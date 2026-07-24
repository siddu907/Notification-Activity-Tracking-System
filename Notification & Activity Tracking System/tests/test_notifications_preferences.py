from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def signup_user(email: str, role: str):
    response = client.post(
        "/auth/signup",
        json={"full_name": email, "email": email, "password": "password123", "role": role},
    )
    assert response.status_code == 200
    return response.json()


def login_user(email: str):
    response = client.post(
        "/auth/login",
        data={"username": email, "password": "password123"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def auth_header(token: str):
    return {"Authorization": f"Bearer {token}"}


def test_project_member_preference_alias_controls_member_added_notifications():
    admin = signup_user("admin-pref@example.com", "Admin")
    member = signup_user("member-pref@example.com", "Member")

    admin_token = login_user(admin["email"])
    member_token = login_user(member["email"])

    project_one = client.post(
        "/projects/",
        json={"name": "Preference Project One", "description": "Test preference updates"},
        headers=auth_header(admin_token),
    ).json()

    preference_response = client.put(
        "/notifications/preferences",
        json={"project_member": False},
        headers=auth_header(member_token),
    )
    assert preference_response.status_code == 200
    assert preference_response.json()["new_project_member"] is False

    add_member_response = client.post(
        f"/projects/{project_one['id']}/members",
        json={"user_id": member["id"]},
        headers=auth_header(admin_token),
    )
    assert add_member_response.status_code == 200

    notifications_response = client.get(
        "/notifications",
        headers=auth_header(member_token),
    )
    assert notifications_response.status_code == 200
    assert notifications_response.json() == []

    project_two = client.post(
        "/projects/",
        json={"name": "Preference Project Two", "description": "Test preference updates"},
        headers=auth_header(admin_token),
    ).json()

    preference_response = client.put(
        "/notifications/preferences",
        json={"project_member": True},
        headers=auth_header(member_token),
    )
    assert preference_response.status_code == 200
    assert preference_response.json()["new_project_member"] is True

    add_member_response = client.post(
        f"/projects/{project_two['id']}/members",
        json={"user_id": member["id"]},
        headers=auth_header(admin_token),
    )
    assert add_member_response.status_code == 200

    notifications_response = client.get(
        "/notifications",
        headers=auth_header(member_token),
    )
    assert notifications_response.status_code == 200
    assert any(item["title"] == "Added to Project" for item in notifications_response.json())


def test_notification_preferences_do_not_expose_project_member_removed():
    user = signup_user("pref-hidden@example.com", "Member")
    token = login_user(user["email"])

    response = client.get(
        "/notifications/preferences",
        headers=auth_header(token),
    )

    assert response.status_code == 200
    payload = response.json()
    assert "project_member_removed" not in payload
