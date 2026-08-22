"""
backup.py -- make a safe, timestamped copy of the database file.

    python scripts/backup.py

It copies db/clinic.sqlite to backups/clinic-YYYY-MM-DD_HHMMSS.sqlite so there
is always a safe copy to fall back on if the live database is damaged or lost.

It uses sqlite3's OWN backup API instead of just copying the file, because a
plain file copy can be corrupt if the database is written to mid-copy. The
backup API copies a consistent snapshot safely, even while the database is in use.

A backup only helps if it is actually run -- a good habit is to run it before
and after any big change.
"""

import sqlite3
from datetime import datetime

# The database and backup locations are decided in ONE place (init_db.py), so
# development and the packaged app each keep their data -- and their backups --
# together in the right folder.
from init_db import DB_FILE, BACKUP_DIR


def make_backup(source_conn=None):
    """Write a safe, timestamped copy of the database and return its path.

    Pass the app's live connection as source_conn (so we snapshot exactly what's
    open); if none is given, we open the database file ourselves. Either way we
    use SQLite's own backup API, which copies a CONSISTENT snapshot even while
    the database is being used -- unlike a plain file copy, which can be corrupt
    if taken mid-write.
    """
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    backup_path = BACKUP_DIR / f"clinic-{stamp}.sqlite"

    own_source = source_conn is None
    source = sqlite3.connect(DB_FILE) if own_source else source_conn
    dest = sqlite3.connect(backup_path)
    try:
        with dest:
            source.backup(dest)
    finally:
        dest.close()
        if own_source:
            source.close()      # only close a connection we opened ourselves
    return backup_path


def main():
    if not DB_FILE.exists():
        print("No database file yet -- run scripts/init_db.py first.")
        return
    print(f"Backup written to: {make_backup()}")


if __name__ == "__main__":
    main()
