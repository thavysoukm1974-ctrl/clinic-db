"""
init_db.py -- create (or re-create) the database file from schema.sql.

Run it from the project root like this:

    python scripts/init_db.py

What it does, step by step:
  1. Find schema.sql and the place the database file should live (db/clinic.sqlite).
  2. Open a connection to that file (SQLite creates the file if it doesn't exist).
  3. Turn foreign keys ON for this connection.
  4. Run every CREATE TABLE statement in schema.sql.

It is SAFE to run more than once: every statement in schema.sql uses
"IF NOT EXISTS", so running again does not wipe your data -- it just makes sure
the tables are there.
"""

import sqlite3
from pathlib import Path

# __file__ is this script. .parent is the scripts/ folder. .parent again is the
# project root. Building paths this way means the script works no matter what
# folder you run it from.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_FILE = PROJECT_ROOT / "schema.sql"
DB_FILE = PROJECT_ROOT / "db" / "clinic.sqlite"


def get_connection(db_path: Path) -> sqlite3.Connection:
    """Open a SQLite connection with foreign keys turned ON.

    We wrap this in a function because EVERY part of the project must connect
    the same way -- always with foreign keys enabled. Do it in one place so we
    can never forget it somewhere else.
    """
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def main() -> None:
    # Make sure the db/ folder exists before SQLite tries to create a file in it.
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)

    schema_sql = SCHEMA_FILE.read_text(encoding="utf-8")

    conn = get_connection(DB_FILE)
    try:
        # executescript runs ALL the statements in the file, not just one.
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()

    print(f"Database ready at: {DB_FILE}")


if __name__ == "__main__":
    main()
