import os
import pytest

os.environ["DATABASE_URL"] = "sqlite:///./test_app.db"

if os.path.exists("test_app.db"):
    os.remove("test_app.db")

from fastapi.testclient import TestClient
from app.database import Base, engine
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def test_db_setup_and_teardown():
    if os.path.exists("test_app.db"):
        engine.dispose()
        os.remove("test_app.db")
    Base.metadata.create_all(bind=engine)
    yield
    engine.dispose()
    if os.path.exists("test_app.db"):
        os.remove("test_app.db")
