import sqlite3

DB_PATH = "familystatus.db"

PRESET_STATUSES = ["Home", "Out", "Busy", "Sleeping"]


# ---------- setup ----------

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS members (
            id   INTEGER PRIMARY KEY,
            name  TEXT NOT NULL UNIQUE
        )
    """)
    # the catalog: every status that exists, preset or custom, stored once
    conn.execute("""
        CREATE TABLE IF NOT EXISTS statuses (
            id        INTEGER PRIMARY KEY,
            text      TEXT NOT NULL UNIQUE,
            is_preset INTEGER NOT NULL DEFAULT 0
        )
    """)
    # link table: which member currently has which status (many-to-many)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS member_statuses (
            member_id INTEGER NOT NULL REFERENCES members(id),
            status_id INTEGER NOT NULL REFERENCES statuses(id),
            PRIMARY KEY (member_id, status_id)
        )
    """)
    # put the presets in the catalog; OR IGNORE skips ones that are already there
    for text in PRESET_STATUSES:
        conn.execute(
            "INSERT OR IGNORE INTO statuses (text, is_preset) VALUES (?, 1)", (text,)
        )
    conn.commit()      # save changes to the file
    conn.close()


# ---------- members ----------

def list_members():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT id, name FROM members").fetchall()
    conn.close()
    return rows

def add_member(name):
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("INSERT INTO members (name) VALUES (?)", (name,))
        conn.commit()
    finally:
        conn.close()  # runs even if the INSERT fails, so no lock is left behind

def delete_member(member_id):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM members WHERE id = ?", (member_id,))
    conn.commit()
    conn.close()


# ---------- statuses (the catalog) ----------

def list_statuses():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT id, text, is_preset FROM statuses").fetchall()
    conn.close()
    return rows

def get_or_create_status(text):
    """Return the id of this status, adding it to the catalog first if it's new."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("INSERT OR IGNORE INTO statuses (text) VALUES (?)", (text,))
        conn.commit()
        row = conn.execute("SELECT id FROM statuses WHERE text = ?", (text,)).fetchone()
        return row[0]
    finally:
        conn.close()


# ---------- member_statuses (who has which status) ----------

def list_member_statuses(member_id):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        """
        SELECT statuses.id, statuses.text
        FROM member_statuses
        JOIN statuses ON statuses.id = member_statuses.status_id
        WHERE member_statuses.member_id = ?
        """,
        (member_id,),
    ).fetchall()
    conn.close()
    return rows

def add_status_to_member(member_id, status_id):
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("PRAGMA foreign_keys = ON")  # SQLite ignores REFERENCES unless this is on
        conn.execute(
            "INSERT INTO member_statuses (member_id, status_id) VALUES (?, ?)",
            (member_id, status_id),
        )
        conn.commit()
    finally:
        conn.close()

def remove_status_from_member(member_id, status_id):
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "DELETE FROM member_statuses WHERE member_id = ? AND status_id = ?",
            (member_id, status_id),
        )
        conn.commit()
    finally:
        conn.close()
