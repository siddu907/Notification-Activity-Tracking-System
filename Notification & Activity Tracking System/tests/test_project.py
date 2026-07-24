from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def register_user(email, role):
    response = client.post("/auth/signup", json={
        "full_name": f"{role} User",
        "email": email,
        "password": "testpass",
        "role": role,
    })
    assert response.status_code == 200
    return response.json()


def login_user(email):
    response = client.post("/auth/login", data={"username": email, "password": "testpass"})
    assert response.status_code == 200
    return response.json()["access_token"]


