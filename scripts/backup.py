"""
backup.py -- make a safe, timestamped copy of the database file.

    python scripts/backup.py

You lost data once; this exists so that never costs you the project again.
It copies db/clinic.sqlite to backups/clinic-YYYY-MM-DD_HHMMSS.sqlite.

We use sqlite3's OWN backup API instead of just copying the file, because a
plain file copy can be corrupt if the database is mid-write. The backup API
copies a consistent snapshot safely, even while the database is in use.

A backup is only useful if you actually run it. Later we can make this run
automatically, but for now: run it before and after any big change.
"""

import sqlite3
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_FILE = PROJECT_ROOT / "db" / "clinic.sqlite"
BACKUP_DIR = PROJECT_ROOT / "backups"


def main():
    if not DB_FILE.exists():
        print("No database file yet -- run scripts/init_db.py first.")
        return

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    backup_path = BACKUP_DIR / f"clinic-{stamp}.sqlite"

    # Open the live database and an empty destination file, then let SQLite copy
    # a clean snapshot from one to the other.
    source = sqlite3.connect(DB_FILE)
    dest = sqlite3.connect(backup_path)
    try:
        with dest:
            source.backup(dest)
    finally:
        dest.close()
        source.close()

    print(f"Backup written to: {backup_path}")


if __name__ == "__main__":
    main()
