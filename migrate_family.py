"""
One-time migration: fixes the family_members table so it matches
the current app.py schema (no user_id column), without losing
any existing rows.

Run this ONCE from your project folder (same folder as rakshacircle.db):

    python migrate_family_members.py

Then restart your Flask server as usual.
"""

import sqlite3

DB_FILE = "rakshacircle.db"

conn = sqlite3.connect(DB_FILE)
conn.row_factory = sqlite3.Row

existing_cols = [
    row["name"]
    for row in conn.execute("PRAGMA table_info(family_members)")
]

print("Current family_members columns:", existing_cols)

if "user_id" not in existing_cols:
    print("No user_id column found — nothing to fix. Exiting.")
    conn.close()
    raise SystemExit

print("Migrating table...")

conn.execute("ALTER TABLE family_members RENAME TO family_members_old")

conn.execute("""
    CREATE TABLE family_members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        relation TEXT,
        phone TEXT,
        email TEXT
    )
""")

conn.execute("""
    INSERT INTO family_members (id, name, relation, phone, email)
    SELECT id, name, relation, phone, email FROM family_members_old
""")

conn.execute("DROP TABLE family_members_old")

conn.commit()

count = conn.execute(
    "SELECT COUNT(*) AS c FROM family_members"
).fetchone()["c"]

print(f"Done. {count} family member(s) carried over successfully.")

conn.close()