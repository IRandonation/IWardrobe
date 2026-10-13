import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[2]
os.environ["DATABASE_URL"] = os.environ.get(
    "IW_TEST_DATABASE_URL",
    "postgresql+psycopg://iwardrobe:local-development@127.0.0.1:5433/iwardrobe_test",
)
os.environ["REDIS_URL"] = "redis://127.0.0.1:6380/15"
os.environ["DATA_DIR"] = str(ROOT / ".local" / "test-data")
assert make_url(os.environ["DATABASE_URL"]).database == "iwardrobe_test", (
    "Tests only run against the dedicated iwardrobe_test database"
)

from iwardrobe.db import SessionLocal, engine  # noqa: E402
from iwardrobe.identity import hasher  # noqa: E402
from iwardrobe.main import app  # noqa: E402
from iwardrobe.models import User  # noqa: E402

ORIGIN = {"Origin": "http://127.0.0.1:5173"}
PASSWORD = "integration-only-password"


@pytest.fixture(scope="session", autouse=True)
def migrated_database():
    command.upgrade(Config(str(ROOT / "backend/alembic.ini")), "head")


@pytest.fixture(autouse=True)
def clean_database(migrated_database):
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE users, login_attempts CASCADE"))
    with SessionLocal() as db:
        for username in ["alice", "bob"]:
            db.add(
                User(username=username, display_name=username, password_hash=hasher.hash(PASSWORD))
            )
        db.commit()
    yield


@pytest.fixture
def client():
    with TestClient(app, headers=ORIGIN) as client:
        yield client


@pytest.fixture
def authenticated(client):
    response = client.post("/api/auth/login", json={"username": "alice", "password": PASSWORD})
    assert response.status_code == 200
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    return client


@pytest.fixture
def bob():
    with TestClient(app, headers=ORIGIN) as client:
        response = client.post("/api/auth/login", json={"username": "bob", "password": PASSWORD})
        client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
        yield client


@pytest.fixture
def image_bytes():
    return (ROOT / "fixtures/demo/images/oat-knit.png").read_bytes()
