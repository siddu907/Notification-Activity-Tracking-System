import uuid
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def _create_admin_and_get_token():
    email = f"admin+{uuid.uuid4().hex[:8]}@example.com"
    signup_response = client.post("/auth/signup", json={
        "full_name": "Export Admin",
        "email": email,
        "password": "testpass",
        "role": "Admin"
    })
    assert signup_response.status_code == 200

    login_response = client.post("/auth/login", data={
        "username": email,
        "password": "testpass"
    })
    assert login_response.status_code == 200
    return login_response.json()["access_token"]


def test_exports_csv_and_pdf_endpoints_do_not_error():
    token = _create_admin_and_get_token()
    headers = {"Authorization": f"Bearer {token}"}

    csv_response = client.get("/exports/activities/csv", headers=headers)
    assert csv_response.status_code == 200
    assert "text/csv" in csv_response.headers["content-type"]
    assert "attachment; filename=activities_" in csv_response.headers["content-disposition"]
    assert csv_response.text.startswith("ID,User ID,User Name")

    audit_csv_response = client.get("/exports/audit-logs/csv", headers=headers)
    assert audit_csv_response.status_code == 200
    assert "text/csv" in audit_csv_response.headers["content-type"]
    assert "attachment; filename=audit_logs_" in audit_csv_response.headers["content-disposition"]
    assert audit_csv_response.text.startswith("ID,Entity Type,Entity ID")

    pdf_response = client.get("/exports/activities/pdf", headers=headers)
    assert pdf_response.status_code == 200
    assert "attachment; filename=activities_" in pdf_response.headers["content-disposition"]
    assert pdf_response.headers["content-type"].startswith("application/pdf")

    audit_pdf_response = client.get("/exports/audit-logs/pdf", headers=headers)
    assert audit_pdf_response.status_code == 200
    assert "attachment; filename=audit_logs_" in audit_pdf_response.headers["content-disposition"]
    assert audit_pdf_response.headers["content-type"].startswith("application/pdf")


def test_export_activities_pdf_handles_raw_action_strings_in_legacy_activity_logs_table():
    from app.database import engine
    from sqlalchemy import text

    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS activity_logs"))
        conn.execute(text("""
            CREATE TABLE activity_logs (
                id INTEGER NOT NULL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                action VARCHAR NOT NULL,
                target_type VARCHAR,
                target_id INTEGER,
                description TEXT,
                created_at DATETIME,
                is_deleted BOOLEAN NOT NULL DEFAULT 0
            )
        """))

    token = _create_admin_and_get_token()
    headers = {"Authorization": f"Bearer {token}"}

    pdf_response = client.get("/exports/activities/pdf", headers=headers)
    assert pdf_response.status_code == 200
    assert "attachment; filename=activities_" in pdf_response.headers["content-disposition"]
    assert pdf_response.headers["content-type"].startswith("application/pdf")


def test_export_audit_logs_endpoints_accept_blank_entity_filters():
    token = _create_admin_and_get_token()
    headers = {"Authorization": f"Bearer {token}"}

    csv_response = client.get(
        "/exports/audit-logs/csv?entity_type=&entity_id=",
        headers=headers,
    )
    assert csv_response.status_code == 200
    assert "text/csv" in csv_response.headers["content-type"]

    pdf_response = client.get(
        "/exports/audit-logs/pdf?entity_type=&entity_id=",
        headers=headers,
    )
    assert pdf_response.status_code == 200
    assert pdf_response.headers["content-type"].startswith("application/pdf")


def test_export_activities_csv_filters_by_action_query_string():
    token = _create_admin_and_get_token()
    headers = {"Authorization": f"Bearer {token}"}

    project_response = client.post(
        "/projects/",
        json={"name": "Export Filter Project", "description": "Action filter regression"},
        headers=headers,
    )
    assert project_response.status_code == 200

    csv_response = client.get(
        "/exports/activities/csv?action=project_created",
        headers=headers,
    )
    assert csv_response.status_code == 200
    assert "Project Created" in csv_response.text
