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
import sys
from pathlib import Path

# __file__ is this script. .parent is the scripts/ folder. .parent again is the
# project root. Building paths this way means the script works no matter what
# folder you run it from.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# The app runs in one of two situations, and the data lives somewhere sensible
# for each -- the user is never asked (they should not need to know or care
# where the internal database file is):
#
#   * Running from source (development): everything stays inside the project
#     folder, as before -- db/ for the database, backups/ for backups.
#
#   * Running as a packaged .exe (PyInstaller sets sys.frozen): data goes to
#     Documents\ClinicDB. Documents rather than the hidden AppData, so the
#     owner can SEE the folder and copy it to a USB stick for safekeeping.
#     The .exe itself unpacks to a throwaway temp folder each run, so data
#     must never live next to the program.
#
# PyInstaller also bundles schema.sql inside the .exe; at run time bundled
# files appear under sys._MEIPASS, so the schema path differs too.
if getattr(sys, "frozen", False):                    # packaged .exe
    DATA_DIR = Path.home() / "Documents" / "ClinicDB"
    SCHEMA_FILE = Path(sys._MEIPASS) / "schema.sql"  # bundled inside the exe
else:                                                # running from source
    DATA_DIR = PROJECT_ROOT
    SCHEMA_FILE = PROJECT_ROOT / "schema.sql"

DB_FILE = DATA_DIR / "db" / "clinic.sqlite"
BACKUP_DIR = DATA_DIR / "backups"


def get_connection(db_path: Path) -> sqlite3.Connection:
    """Open a SQLite connection with foreign keys turned ON.

    We wrap this in a function because EVERY part of the project must connect
    the same way -- always with foreign keys enabled. Do it in one place so we
    can never forget it somewhere else.
    """
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def ensure_database() -> None:
    """Make sure the database file and all its tables exist.

    Safe to run every single start-up: the folder creation ignores an existing
    folder, and every statement in schema.sql uses IF NOT EXISTS, so on an
    already-set-up machine this changes nothing. On a brand-new machine (first
    run of the packaged app) it quietly builds the empty database.
    """
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    schema_sql = SCHEMA_FILE.read_text(encoding="utf-8")
    conn = get_connection(DB_FILE)
    try:
        # executescript runs ALL the statements in the file, not just one.
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()


def main() -> None:
    ensure_database()
    print(f"Database ready at: {DB_FILE}")


if __name__ == "__main__":
    main()
