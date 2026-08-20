"""
sales.py -- record a sale AND subtract the stock. The core operation of the system.

A sale (a "receipt") can contain several different medicines at once. Selling
reduces the right batches, refuses to oversell, and remembers which batch each
unit came from. (The simpler `record_sale` inside sample_data.py is only a
seeder for test data and does NOT touch stock -- this is the real logic.)

To try it on the sample database:
    python scripts/sales.py
"""

from datetime import datetime

from init_db import DB_FILE, get_connection
from stock import batches_for


def record_sale(conn, items, visit_id=None):
    """Record ONE sale (a receipt) that may contain several medicines.

    `items` is a list of (medicine_id, quantity) pairs -- one entry per medicine
    on the receipt. Each medicine is sold at its current price, frozen onto the
    sale. Returns the new sale_id.

    A receipt is ALL-OR-NOTHING: if ANY medicine on it lacks stock, nothing is
    saved at all -- no sale row, no stock change. That is why the stock check
    happens fully BEFORE any writing.

    The work is split in two:
      * this function handles the whole receipt (the check + the sale header),
      * _fill_one_line() handles one medicine's line (the batch-by-batch taking).
    """
    if not items:
        raise ValueError("a sale needs at least one item")
    for _medicine_id, quantity in items:
        if quantity <= 0:
            raise ValueError("quantity must be positive")

    # 1. GUARD: check EVERY line has enough stock BEFORE writing anything.
    #    (Assumes each medicine appears at most once on the receipt; if the same
    #     medicine is bought twice, combine it into one line first.)
    for medicine_id, quantity in items:
        available = sum(qty for (_id, qty, _exp, _rec) in batches_for(conn, medicine_id))
        if quantity > available:
            raise ValueError(
                f"Not enough stock for {_medicine_name(conn, medicine_id)}: "
                f"asked {quantity}, only {available} on hand."
            )

    # 2. One sale header for the whole receipt (NULL visit_id = a walk-in).
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sale_id = conn.execute(
        "INSERT INTO sales (sale_datetime, visit_id) VALUES (?, ?)", (now, visit_id)
    ).lastrowid

    # 3. Fill each medicine's line from its batches (soonest-expiry first).
    for medicine_id, quantity in items:
        _fill_one_line(conn, sale_id, medicine_id, quantity)

    # 4. One commit makes the ENTIRE receipt permanent at once (all-or-nothing).
    conn.commit()
    return sale_id


def _fill_one_line(conn, sale_id, medicine_id, quantity):
    """Take `quantity` units of ONE medicine and add it to an existing sale.

    Walk the medicine's batches soonest-expiry-first (FEFO): take units from each
    batch in turn, record which batch they came from, freeze the price, and
    subtract the stock. If one batch runs short, continue into the next batch.
    The caller has already checked there is enough stock and created the sale.
    """
    # Freeze the price now, so a later price change never rewrites this receipt.
    unit_price = conn.execute(
        "SELECT unit_price FROM medicines WHERE id = ?", (medicine_id,)
    ).fetchone()[0]

    remaining = quantity
    for batch_id, batch_qty, _expiry, _received in batches_for(conn, medicine_id):
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


def _medicine_name(conn, medicine_id):
    """Look up a medicine's name (used only for clear error messages)."""
    row = conn.execute(
        "SELECT name FROM medicines WHERE id = ?", (medicine_id,)
    ).fetchone()
    return row[0] if row else f"medicine #{medicine_id}"


def _medicine_id(conn, name):
    """Look up a medicine's id by name (used by the demo below)."""
    return conn.execute(
        "SELECT id FROM medicines WHERE name = ?", (name,)
    ).fetchone()[0]


def _show(conn, medicine_id, label):
    """Print a medicine's remaining batches, so before/after is easy to see."""
    print(label)
    rows = batches_for(conn, medicine_id)
    if not rows:
        print("    (no stock left)")
    for batch_id, qty, expiry, _rec in rows:
        print(f"    batch {batch_id}: {qty:>4} left, expires {expiry}")


def main():
    """Demonstration on the sample data: sell a receipt with TWO medicines at
    once, showing stock before and after and the computed receipt total."""
    conn = get_connection(DB_FILE)
    try:
        para = _medicine_id(conn, "Paracetamol")
        vitc = _medicine_id(conn, "Vitamin C")

        print("BEFORE:")
        _show(conn, para, "  Paracetamol")
        _show(conn, vitc, "  Vitamin C")

        # One receipt, two different medicines.
        sale_id = record_sale(conn, [(para, 2), (vitc, 3)])
        print(f"\n-> recorded receipt #{sale_id} with 2 medicines\n")

        print("AFTER:")
        _show(conn, para, "  Paracetamol")
        _show(conn, vitc, "  Vitamin C")

        # The receipt total is COMPUTED from its lines -- never stored.
        total = conn.execute(
            "SELECT SUM(quantity * unit_price) FROM sale_items WHERE sale_id = ?",
            (sale_id,),
        ).fetchone()[0]
        print(f"\nReceipt total (computed from the lines): {total}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
