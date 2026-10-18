import sqlite3

DB_PATH = "familystatus.db"

PRESET_STATUSES = ["Home", "Out", "Busy", "Sleeping"]


# ---------- setup ----------

def init_db():
    conn = sqlite3.connect(DB_PATH)
    # a real person who logs in (one Google account = one user)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id    INTEGER PRIMARY KEY,
            email TEXT NOT NULL UNIQUE
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS families (
            id   INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS members (
            id        INTEGER PRIMARY KEY,
            family_id INTEGER NOT NULL REFERENCES families(id),
            user_id   INTEGER REFERENCES users(id),  -- NULL = member without a login (e.g. Grandma)
            name      TEXT NOT NULL,
            UNIQUE (family_id, name)  -- no two "Dad"s in the same family
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
            until     TEXT,  -- when it expires (UTC time); NULL = until changed
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

def list_members(family_id):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT id, name FROM members WHERE family_id = ?", (family_id,)
    ).fetchall()
    conn.close()
    return rows

def add_member(family_id, name):
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT INTO members (family_id, name) VALUES (?, ?)", (family_id, name)
        )
        conn.commit()
    finally:
        conn.close()  # runs even if the INSERT fails, so no lock is left behind

def delete_member(member_id):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM members WHERE id = ?", (member_id,))
    conn.commit()
    conn.close()


# ---------- users (people who log in) ----------

def get_or_create_user(email):
    """Return the id of the user with this email, creating them on first login."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("INSERT OR IGNORE INTO users (email) VALUES (?)", (email,))
        conn.commit()
        row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        return row[0]
    finally:
        conn.close()

def list_families_for_user(user_id):
    """[(family_id, family_name), ...] for every family this user is a member of."""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        """
        SELECT families.id, families.name FROM members
        JOIN families ON families.id = members.family_id
        WHERE members.user_id = ?
        ORDER BY families.id
        """,
        (user_id,),
    ).fetchall()
    conn.close()
    return rows

def is_member_of(user_id, family_id):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT 1 FROM members WHERE user_id = ? AND family_id = ?", (user_id, family_id)
    ).fetchone()
    conn.close()
    return row is not None


# ---------- families ----------

class DuplicateFamilyName(Exception):
    """This user is already in a family with that name."""

def create_family(family_name, user_id, member_name):
    """Create a family and make this user its first member. Returns the new family id."""
    conn = sqlite3.connect(DB_PATH)
    try:
        # rule: one person can't be in two families with the same name
        already = conn.execute(
            """
            SELECT 1 FROM members
            JOIN families ON families.id = members.family_id
            WHERE members.user_id = ? AND families.name = ?
            """,
            (user_id, family_name),
        ).fetchone()
        if already:
            raise DuplicateFamilyName(family_name)

        cur = conn.execute("INSERT INTO families (name) VALUES (?)", (family_name,))
        family_id = cur.lastrowid  # the id SQLite just created
        conn.execute(
            "INSERT INTO members (family_id, user_id, name) VALUES (?, ?, ?)",
            (family_id, user_id, member_name),
        )
        conn.commit()  # one commit: both rows are saved, or neither is
        return family_id
    finally:
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

def list_member_statuses(member_id, now):
    """Statuses this member has right now; expired ones are skipped."""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        """
        SELECT statuses.id, statuses.text
        FROM member_statuses
        JOIN statuses ON statuses.id = member_statuses.status_id
        WHERE member_statuses.member_id = ?
          AND (member_statuses.until IS NULL OR member_statuses.until > ?)
        """,
        (member_id, now),
    ).fetchall()
    conn.close()
    return rows

def add_status_to_member(member_id, status_id, until=None):
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("PRAGMA foreign_keys = ON")  # SQLite ignores REFERENCES unless this is on
        # if they already have this status, just update how long it lasts
        conn.execute(
            """
            INSERT INTO member_statuses (member_id, status_id, until) VALUES (?, ?, ?)
            ON CONFLICT (member_id, status_id) DO UPDATE SET until = excluded.until
            """,
            (member_id, status_id, until),
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
