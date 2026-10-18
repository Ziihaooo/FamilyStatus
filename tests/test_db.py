import sqlite3

import pytest

from app import db


def make_family(name="Lim"):
    with db.connect() as conn:
        return conn.execute("INSERT INTO families (name) VALUES (?)", (name,)).lastrowid


def test_add_and_list_member(fresh_db):
    family = make_family()
    db.add_member(family, "Dad")

    assert db.list_members(family) == [(1, "Dad")]

def test_delete_member(fresh_db):
    family = make_family()
    db.add_member(family, "Mom")
    db.add_member(family, "Dad")
    db.delete_member(1)

    assert db.list_members(family) == [(2, "Dad")]


def test_member_needs_a_real_family(fresh_db):
    # foreign keys are on: a member can't point to a family that doesn't exist
    with pytest.raises(sqlite3.IntegrityError):
        db.add_member(999, "Ghost")
