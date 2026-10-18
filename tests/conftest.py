import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app, current_family_id, current_user_id


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    """Empty throwaway database, so tests never touch familystatus.db."""
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()


@pytest.fixture
def client(fresh_db):
    """A browser that is 'logged in' as a user who owns family 1 (no Google needed)."""
    user_id = db.get_or_create_user("tester@example.com")
    family_id = db.create_family("Test family", user_id, "Tester")  # also adds member 1

    app.dependency_overrides[current_user_id] = lambda: user_id
    app.dependency_overrides[current_family_id] = lambda: family_id
    yield TestClient(app)
    app.dependency_overrides.clear()
