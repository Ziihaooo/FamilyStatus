"""Access control: try the attacks and make sure they fail."""

from fastapi.testclient import TestClient

from app import db
from app.main import app

BUSY = 3  # preset status id


def statuses_of(member_id):
    return db.list_member_statuses(member_id, "2000-01-01")


def test_logged_out_cannot_change_status(fresh_db):
    family_id = db.create_family("Lim", db.get_or_create_user("a@x.com"), "Dad")
    dad = db.list_members(family_id)[0][0]

    r = TestClient(app).post(f"/members/{dad}/statuses", data={"status_id": BUSY})

    assert r.status_code == 404
    assert statuses_of(dad) == []


def test_cannot_change_member_of_another_family(client):
    # `client` is logged in to its own family; the Tan family is someone else's
    tan_family = db.create_family("Tan", db.get_or_create_user("tan@x.com"), "Mr Tan")
    mr_tan = db.list_members(tan_family)[0][0]

    r1 = client.post(f"/members/{mr_tan}/statuses", data={"status_id": BUSY})
    r2 = client.post(f"/members/{mr_tan}/statuses/custom", data={"text": "hacked"})
    r3 = client.post(f"/members/{mr_tan}/statuses/{BUSY}/remove")

    assert (r1.status_code, r2.status_code, r3.status_code) == (404, 404, 404)
    assert statuses_of(mr_tan) == []


def test_can_change_member_of_own_family(client):
    me = db.list_members(1)[0][0]  # the logged-in tester, in family 1

    r = client.post(f"/members/{me}/statuses", data={"status_id": BUSY})

    assert r.status_code == 200
    assert statuses_of(me) == [(BUSY, "Busy")]
