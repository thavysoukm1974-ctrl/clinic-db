"""
sample_data.py -- fill the database with FAKE data so we can test and learn.

    python scripts/sample_data.py

IMPORTANT: this is pretend data (from the plan: "No real data in the test
system"). It's here so you can see the tables working -- run a report, check
an expiring batch -- without needing the shop's real records.

It is safe to run more than once, but it ADDS a fresh set each time, so you'll
get duplicates. To start clean, delete db/clinic.sqlite and run init_db.py again.

Read this file to see, in plain Python, HOW rows get inserted -- especially how
a sale is made of one row in `sales` plus several rows in `sale_items`.
"""

from datetime import date, datetime, timedelta

# Reuse the exact same connection helper the rest of the project uses, so
# foreign keys are always ON. (init_db.py lives next to this file.)
from init_db import DB_FILE, get_connection


def insert_medicines(conn):
    """Add a few products to the catalog. Returns their new ids by name."""
    rows = [
        # (name, form, category, unit_price, reorder_threshold)
        ("Paracetamol 500mg", "tablet", "painkiller", 5.00, 20),
        ("Amoxicillin 250mg", "capsule", "antibiotic", 12.00, 10),
        ("Cough Syrup 100ml", "syrup", "cold & flu", 8.50, 5),
        ("Vitamin C 1000mg", "tablet", "vitamin", 3.00, 15),
    ]
    ids = {}
    for name, form, category, price, threshold in rows:
        cur = conn.execute(
            """INSERT INTO medicines (name, form, category, unit_price, reorder_threshold)
               VALUES (?, ?, ?, ?, ?)""",
            (name, form, category, price, threshold),
        )
        # cur.lastrowid is the id SQLite just assigned to the row we inserted.
        ids[name] = cur.lastrowid
    return ids


def insert_batches(conn, med_ids):
    """Add stock lots. One medicine gets a batch that expires SOON, on purpose,
    so the 'expiring soon' warning has something to find."""
    today = date.today()
    soon = today + timedelta(days=20)    # expires in ~3 weeks -> should trigger a warning
    later = today + timedelta(days=400)  # safely far away

    rows = [
        # (medicine name, quantity, purchase_price, received_date, expiry_date)
        ("Paracetamol 500mg", 100, 3.00, today.isoformat(), later.isoformat()),
        ("Amoxicillin 250mg",   8, 8.00, today.isoformat(), soon.isoformat()),   # low stock AND expiring
        ("Cough Syrup 100ml",  30, 5.50, today.isoformat(), later.isoformat()),
        ("Vitamin C 1000mg",  200, 1.50, today.isoformat(), later.isoformat()),
    ]
    for name, qty, cost, received, expiry in rows:
        conn.execute(
            """INSERT INTO batches
                   (medicine_id, quantity, purchase_price, received_date, expiry_date)
               VALUES (?, ?, ?, ?, ?)""",
            (med_ids[name], qty, cost, received, expiry),
        )


def insert_one_sample_sale(conn, med_ids):
    """Create ONE example sale to show the sales/sale_items relationship.

    A sale is TWO steps:
      1. insert the receipt into `sales`  -> gives us a sale_id
      2. insert each line into `sale_items`, all pointing at that sale_id
    (Decreasing stock in `batches` is deliberately NOT done here -- that's the
    logic we'll build together, so you understand it fully.)
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # The lines we want to sell: (medicine name, quantity, unit_price)
    lines = [
        ("Paracetamol 500mg", 2, 5.00),
        ("Vitamin C 1000mg",  1, 3.00),
    ]
    total = sum(qty * price for _name, qty, price in lines)

    # Step 1: the receipt.
    cur = conn.execute(
        "INSERT INTO sales (sale_datetime, total_amount) VALUES (?, ?)",
        (now, total),
    )
    sale_id = cur.lastrowid

    # Step 2: the lines, each tied to sale_id.
    for name, qty, price in lines:
        conn.execute(
            """INSERT INTO sale_items (sale_id, medicine_id, quantity, unit_price)
               VALUES (?, ?, ?, ?)""",
            (sale_id, med_ids[name], qty, price),
        )


def main():
    conn = get_connection(DB_FILE)
    try:
        med_ids = insert_medicines(conn)
        insert_batches(conn, med_ids)
        insert_one_sample_sale(conn, med_ids)
        conn.commit()
    finally:
        conn.close()

    print("Sample data inserted. Open db/clinic.sqlite in DBeaver to look around.")


if __name__ == "__main__":
    main()
