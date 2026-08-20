"""
sales.py -- record a sale AND subtract the stock. The core operation of the system.

Selling here reduces the right batches, refuses to oversell, and remembers which
batch each unit came from. (The simpler `record_sale` inside sample_data.py is
only a seeder for test data and does NOT touch stock -- this is the real logic.)

To try it on the sample database:
    python scripts/sales.py
"""

from datetime import datetime

from init_db import DB_FILE, get_connection
from stock import batches_for, current_stock


def record_sale(conn, medicine_id, quantity, unit_price=None, visit_id=None):
    """Sell `quantity` units of ONE medicine. Returns the new sale_id.

    It does four things, in order -- and either ALL of them happen or NONE do:

      1. GUARD -- refuse if we don't have enough stock. We check BEFORE writing
         anything, so a sale that can't be filled changes nothing in the database.
      2. FREEZE THE PRICE -- default to the medicine's current price, then copy
         it onto the sale so a future price change never rewrites this receipt.
      3. CREATE THE SALE header (optionally tied to a visit via visit_id).
      4. WALK THE BATCHES soonest-expiry-first (FEFO): take units from each batch
         in turn, record which batch each line came from, and subtract the stock.
         If one batch runs short, the sale spills into the next batch.
    """
    if quantity <= 0:
        raise ValueError("quantity must be positive")

    # Batches that still have stock, SOONEST-EXPIRY FIRST (this is the FEFO order).
    batches = batches_for(conn, medicine_id)
    available = sum(batch_qty for (_id, batch_qty, _exp, _rec) in batches)

    # 1. GUARD: never sell more than we physically have.
    if quantity > available:
        raise ValueError(
            f"Not enough stock: asked for {quantity}, only {available} on hand."
        )

    # 2. Freeze the price (see sale_items in schema.sql for WHY we copy it).
    if unit_price is None:
        unit_price = conn.execute(
            "SELECT unit_price FROM medicines WHERE id = ?", (medicine_id,)
        ).fetchone()[0]

    # 3. The sale header. visit_id is NULL for a walk-in, or set if given in a visit.
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur = conn.execute(
        "INSERT INTO sales (sale_datetime, visit_id) VALUES (?, ?)", (now, visit_id)
    )
    sale_id = cur.lastrowid

    # 4. Take units from each batch until the order is filled.
    remaining = quantity
    for batch_id, batch_qty, _expiry, _received in batches:
        if remaining == 0:
            break
        take = min(remaining, batch_qty)   # all we still need, or all this batch has

        # Record the line, remembering WHICH batch these units came from ...
        conn.execute(
            """INSERT INTO sale_items (sale_id, medicine_id, batch_id, quantity, unit_price)
               VALUES (?, ?, ?, ?, ?)""",
            (sale_id, medicine_id, batch_id, take, unit_price),
        )
        # ... and subtract them from that batch's stock.
        conn.execute(
            "UPDATE batches SET quantity = quantity - ? WHERE id = ?", (take, batch_id)
        )
        remaining -= take

    # Nothing was saved until here; commit makes all of step 3+4 permanent at once.
    conn.commit()
    return sale_id


def _show(conn, medicine_id, label):
    """Small helper: print a medicine's batches so we can see before/after."""
    print(label)
    for batch_id, qty, expiry, _rec in batches_for(conn, medicine_id):
        print(f"    batch {batch_id}: {qty:>4} left, expires {expiry}")
    if not batches_for(conn, medicine_id):
        print("    (no stock left)")


def main():
    """A tiny demonstration on the sample data: sell 5 Paracetamol, showing the
    batches before and after so you can watch stock go down."""
    conn = get_connection(DB_FILE)
    try:
        med_id = conn.execute(
            "SELECT id FROM medicines WHERE name = 'Paracetamol'"
        ).fetchone()[0]

        _show(conn, med_id, "Paracetamol BEFORE selling:")
        sale_id = record_sale(conn, med_id, 5)
        print(f"\n-> recorded sale #{sale_id}: sold 5 Paracetamol\n")
        _show(conn, med_id, "Paracetamol AFTER selling:")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
