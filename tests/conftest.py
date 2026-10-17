import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    """Empty throwaway database, so tests never touch familystatus.db."""
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()


@pytest.fixture
def client(fresh_db):
    return TestClient(app)
