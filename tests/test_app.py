from app import db


def test_add_member_via_form(client):
    r = client.post("/members", data={"name": "  Dad  "}, follow_redirects=False)

    assert r.status_code == 303
    assert db.list_members() == [(1, "Dad")]  # spaces stripped


def test_duplicate_name_shows_error(client):
    client.post("/members", data={"name": "Dad"})
    r = client.post("/members", data={"name": "Dad"})

    assert "already exists" in r.text
    assert len(db.list_members()) == 1


def test_blank_name_rejected(client):
    client.post("/members", data={"name": "   "})

    assert db.list_members() == []


def test_too_long_name_rejected(client):
    r = client.post("/members", data={"name": "x" * 41})

    assert r.status_code == 422
    assert db.list_members() == []


def test_name_is_html_escaped(client):
    client.post("/members", data={"name": "<script>alert(1)</script>"})
    body = client.get("/").text

    assert "<script>alert(1)</script>" not in body
    assert "&lt;script&gt;" in body
