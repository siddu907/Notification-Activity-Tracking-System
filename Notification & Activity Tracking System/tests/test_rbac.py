from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def signup_user(full_name: str, email: str, role: str):
    response = client.post(
        "/auth/signup",
        json={"full_name": full_name, "email": email, "password": "password123", "role": role},
    )
    assert response.status_code == 200
    return response.json()


def login_user(email: str):
    response = client.post("/auth/login", data={"username": email, "password": "password123"})
    assert response.status_code == 200
    return response.json()["access_token"]


def auth_header(token: str):
    return {"Authorization": f"Bearer {token}"}


def test_admin_user_management():
    admin = signup_user("Admin User", "admin-user@example.com", "Admin")
    member = signup_user("Member User", "member-user@example.com", "Member")

    admin_token = login_user(admin["email"])
    admin_headers = auth_header(admin_token)

    response = client.get("/users/", headers=admin_headers)
    assert response.status_code == 200
    assert any(u["email"] == admin["email"] for u in response.json())

    response = client.put(
        f"/users/{member['id']}",
        json={"full_name": "Updated Member", "role": "Manager"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["full_name"] == "Updated Member"
    assert response.json()["role"] == "Manager"

    response = client.delete(f"/users/{member['id']}", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["detail"] == "User deleted"


def test_manager_can_access_user_list_and_detail():
    admin = signup_user("Admin3", "admin3@example.com", "Admin")
    manager = signup_user("Manager3", "manager3@example.com", "Manager")
    admin_token = login_user(admin["email"])
    manager_token = login_user(manager["email"])
    manager_headers = auth_header(manager_token)

    response = client.get("/users/", headers=manager_headers)
    assert response.status_code == 200
    assert any(u["email"] == manager["email"] for u in response.json())

    response = client.get(f"/users/{admin['id']}", headers=manager_headers)
    assert response.status_code == 200
    assert response.json()["email"] == admin["email"]


def test_rbac_and_soft_delete_for_projects_and_tasks():
    admin = signup_user("Admin2", "admin2@example.com", "Admin")
    manager = signup_user("Manager2", "manager2@example.com", "Manager")
    member = signup_user("Member2", "member2@example.com", "Member")
    admin_token = login_user(admin["email"])
    manager_token = login_user(manager["email"])
    member_token = login_user(member["email"])

    project = client.post(
        "/projects/",
        json={"name": "RBAC Project", "description": "RBAC test project"},
        headers=auth_header(admin_token),
    ).json()
    project_id = project["id"]

    client.post(
        f"/projects/{project_id}/members",
        json={"user_id": manager["id"]},
        headers=auth_header(admin_token),
    )
    client.post(
        f"/projects/{project_id}/members",
        json={"user_id": member["id"]},
        headers=auth_header(admin_token),
    )

    response = client.post(
        "/projects/",
        json={"name": "Member Project", "description": "Should fail"},
        headers=auth_header(member_token),
    )
    assert response.status_code == 403

    task = client.post(
        "/tasks/",
        json={
            "title": "RBAC Task",
            "description": "RBAC task content",
            "status": "Pending",
            "priority": "Medium",
            "due_date": "2026-08-10T00:00:00",
            "assigned_to": member["id"],
            "project_id": project_id,
        },
        headers=auth_header(manager_token),
    ).json()
    task_id = task["id"]

    response = client.put(
        f"/tasks/{task_id}",
        json={"status": "In Progress", "priority": "High"},
        headers=auth_header(member_token),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "In Progress"

    response = client.put(
        f"/tasks/{task_id}",
        json={"title": "Should not update name", "description": "No", "status": "Completed"},
        headers=auth_header(member_token),
    )
    assert response.status_code == 400

    response = client.delete(f"/tasks/{task_id}", headers=auth_header(manager_token))
    assert response.status_code == 200
    assert response.json()["detail"] == "Task deleted"

    response = client.get("/tasks/", headers=auth_header(manager_token))
    assert response.status_code == 200
    assert all(task_item["is_deleted"] is False for task_item in response.json())

    response = client.delete(f"/projects/{project_id}", headers=auth_header(admin_token))
    assert response.status_code == 200
    assert response.json()["detail"] == "Project deleted"

    response = client.get("/projects/", headers=auth_header(admin_token))
    assert response.status_code == 200
    assert all(project_item["is_deleted"] is False for project_item in response.json())


def test_exact_project_and_task_routes_with_failures():
    admin = signup_user("Admin4", "admin4@example.com", "Admin")
    manager = signup_user("Manager4", "manager4@example.com", "Manager")
    member = signup_user("Member4", "member4@example.com", "Member")
    outsider = signup_user("Outsider", "outsider@example.com", "Member")
    admin_token = login_user(admin["email"])
    manager_token = login_user(manager["email"])
    member_token = login_user(member["email"])
    outsider_token = login_user(outsider["email"])

    project = client.post(
        "/projects/",
        json={"name": "Exact Project", "description": "Exact route coverage"},
        headers=auth_header(admin_token),
    ).json()
    project_id = project["id"]

    client.post(
        f"/projects/{project_id}/members",
        json={"user_id": manager["id"]},
        headers=auth_header(admin_token),
    )
    client.post(
        f"/projects/{project_id}/members",
        json={"user_id": member["id"]},
        headers=auth_header(admin_token),
    )

    response = client.get(f"/projects/{project_id}", headers=auth_header(manager_token))
    assert response.status_code == 200
    assert response.json()["id"] == project_id

    response = client.get(f"/projects/{project_id}", headers=auth_header(member_token))
    assert response.status_code == 200
    assert response.json()["name"] == "Exact Project"

    response = client.get(f"/projects/{project_id}", headers=auth_header(outsider_token))
    assert response.status_code == 403

    response = client.put(
        f"/projects/{project_id}",
        json={"name": "Exact Project Updated", "description": "Updated details"},
        headers=auth_header(manager_token),
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Exact Project Updated"

    response = client.put(
        f"/projects/{project_id}",
        json={"name": "Fail Update", "description": "Should fail"},
        headers=auth_header(member_token),
    )
    assert response.status_code == 403

    task = client.post(
        "/tasks/",
        json={
            "title": "Exact Task",
            "description": "Exact task route",
            "status": "Pending",
            "priority": "High",
            "due_date": "2026-08-25T00:00:00",
            "assigned_to": member["id"],
            "project_id": project_id,
        },
        headers=auth_header(manager_token),
    ).json()
    task_id = task["id"]

    response = client.get(f"/tasks/{task_id}", headers=auth_header(member_token))
    assert response.status_code == 200
    assert response.json()["id"] == task_id

    response = client.get(f"/tasks/{task_id}", headers=auth_header(outsider_token))
    assert response.status_code == 403

    response = client.put(
        f"/tasks/{task_id}",
        json={"title": "Should fail rename"},
        headers=auth_header(member_token),
    )
    assert response.status_code == 400

    response = client.put(
        f"/tasks/{task_id}",
        json={"status": "Completed"},
        headers=auth_header(member_token),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "Completed"

    response = client.delete(f"/projects/{project_id}", headers=auth_header(admin_token))
    assert response.status_code == 200

    response = client.get(f"/projects/{project_id}", headers=auth_header(admin_token))
    assert response.status_code == 404
