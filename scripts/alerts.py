"""
alerts.py -- read-only warnings built from the data: what is expiring, what is
low on stock. Nothing here changes the database, so it is safe to run any time.

    python scripts/alerts.py

Both alerts are COMPUTED from the raw batches, not stored anywhere. That means
they are always up to date: sell something or receive new stock, and the next
time an alert runs it simply reflects the current numbers.
"""

from datetime import date, timedelta

from init_db import DB_FILE, get_connection


def expiring_soon(conn, days=30):
    """Return batches that still have stock and expire within `days` from today
    (this INCLUDES batches that already expired). Soonest/most urgent first.

    Each row is (medicine_name, batch_id, quantity, expiry_date, days_left),
    where days_left is negative if the batch is already past its expiry date.

    The cutoff date is worked out once in Python, then the database returns every
    batch whose expiry is on or before it. Because dates are stored as ISO text
    ("2026-09-19"), comparing them with <= also compares them in date order.
    """
    today = date.today()
    cutoff = (today + timedelta(days=days)).isoformat()

    rows = conn.execute(
        """
        SELECT m.name, b.id, b.quantity, b.expiry_date
        FROM batches b
        JOIN medicines m ON m.id = b.medicine_id
        WHERE b.quantity > 0
          AND b.expiry_date IS NOT NULL
          AND b.expiry_date <= ?
        ORDER BY b.expiry_date ASC
        """,
        (cutoff,),
    ).fetchall()

    # Add days_left (how many days until expiry; negative = already expired).
    result = []
    for name, batch_id, quantity, expiry_date in rows:
        days_left = (date.fromisoformat(expiry_date) - today).days
        result.append((name, batch_id, quantity, expiry_date, days_left))
    return result


def low_stock(conn):
    """Return active medicines whose USABLE stock on hand is at or below their
    reorder threshold -- i.e. it is time to reorder. Lowest first.

    "Usable" = in stock and NOT expired, the same rule as current_stock and
    batches_for. This matters: expired units must not hide a shortage. A medicine
    with 2 good + 8 expired and a threshold of 5 has only 2 sellable, so it counts
    as 2 and is correctly flagged to reorder.

    Each row is (medicine_name, on_hand, reorder_threshold).

      LEFT JOIN ... ON (not expired) -- sum only the usable batches, but keep the
                                        medicine even if it has none (shows 0).
      HAVING on_hand <= reorder_threshold -- keep only those at the reorder point.
                                            (<= not < so hitting the threshold
                                            exactly still counts as "reorder".)
    """
    today = date.today().isoformat()
    return conn.execute(
        """
        SELECT m.name,
               COALESCE(SUM(b.quantity), 0) AS on_hand,
               m.reorder_threshold
        FROM medicines m
        LEFT JOIN batches b
               ON b.medicine_id = m.id
              AND b.quantity > 0
              AND (b.expiry_date IS NULL OR b.expiry_date >= ?)
        WHERE m.is_active = 1
        GROUP BY m.id
        HAVING on_hand <= m.reorder_threshold
        ORDER BY on_hand ASC
        """,
        (today,),
    ).fetchall()


def main():
    conn = get_connection(DB_FILE)
    try:
        print("=== EXPIRING SOON (within 30 days, including already expired) ===")
        rows = expiring_soon(conn, days=30)
        if not rows:
            print("  nothing expiring soon")
        for name, batch_id, quantity, expiry_date, days_left in rows:
            if days_left < 0:
                when = f"EXPIRED {-days_left} days ago"
            else:
                when = f"in {days_left} days"
            print(f"  {name:<16} batch {batch_id}: {quantity:>4} units, {expiry_date} ({when})")

        print("\n=== LOW ON STOCK (at or below reorder threshold) ===")
        rows = low_stock(conn)
        if not rows:
            print("  nothing low on stock")
        for name, on_hand, threshold in rows:
            print(f"  {name:<16} {on_hand:>4} on hand (reorder at {threshold})")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
