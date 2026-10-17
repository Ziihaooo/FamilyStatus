from app import db


def test_add_and_list_member(tmp_path, monkeypatch):
    # use a temporary database, so tests never touch your real familystatus.db
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))

    db.init_db()
    db.add_member("Dad")

    assert db.list_members() == [(1, "Dad")]

def test_delete_member(tmp_path, monkeypatch):
    # use a temporary database, so tests never touch your real familystatus.db
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))

    db.init_db()
    db.add_member("Mom")
    db.add_member("Dad")
    db.delete_member(1)

    assert db.list_members() == [(2, "Dad")]