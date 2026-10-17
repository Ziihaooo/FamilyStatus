import sqlite3

DB_PATH = "familystatus.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS members (
            id   INTEGER PRIMARY KEY,
            name  TEXT NOT NULL
        )
    """)
    conn.commit()      # save changes to the file
    conn.close()


def list_members():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT name FROM members").fetchall()
    conn.close()
    return rows

def add_member(name):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO members (name) VALUES (?)", (name,))
    conn.commit()
    conn.close()

def delete_member(name):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM members WHERE name = ?", (name,))
    conn.commit()
    conn.close()