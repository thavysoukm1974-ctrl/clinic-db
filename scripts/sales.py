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
    sale.

    Policy for a medicine that is short on stock: "full lines only". If a
    medicine cannot be filled COMPLETELY, it is left off the sale entirely (never
    sold partially) -- but the other medicines that CAN be filled are still sold.
    The skipped medicines are reported back so the seller can tell the customer.

    Returns a pair (sale_id, skipped):
      * sale_id -- the new sale's id, or None if nothing at all could be sold,
      * skipped -- a list of (medicine_id, requested, available) left off.

    Note this is separate from transactional safety: whatever sale we DO make is
    still all-or-nothing at the database level (one commit at the end), so we can
    never record stock going down without the matching sale. "Full lines only" is
    the business choice about WHICH medicines end up on the receipt.
    """
    if not items:
        raise ValueError("a sale needs at least one item")
    for _medicine_id, quantity in items:
        if quantity <= 0:
            raise ValueError("quantity must be positive")

    # 1. Sort the requested medicines into "can fully fill" vs "short".
    #    (Assumes each medicine appears at most once on the receipt; if the same
    #     medicine is bought twice, combine it into one line first.)
    to_sell = []   # (medicine_id, quantity) we will actually sell
    skipped = []   # (medicine_id, requested, available) left off, short on stock
    for medicine_id, quantity in items:
        available = sum(qty for (_id, qty, _exp, _rec) in batches_for(conn, medicine_id))
        if quantity <= available:
            to_sell.append((medicine_id, quantity))
        else:
            skipped.append((medicine_id, quantity, available))

    # 2. If not a single medicine can be filled, don't create an empty sale.
    if not to_sell:
        return None, skipped

    # 3. One sale header for the medicines we can fill (NULL visit_id = walk-in).
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sale_id = conn.execute(
        "INSERT INTO sales (sale_datetime, visit_id) VALUES (?, ?)", (now, visit_id)
    ).lastrowid

    # 4. Fill each sellable line from its batches (soonest-expiry first).
    for medicine_id, quantity in to_sell:
        _fill_one_line(conn, sale_id, medicine_id, quantity)

    # 5. One commit makes the whole (fillable) sale permanent at once.
    conn.commit()
    return sale_id, skipped


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
    """Demonstration on the sample data: a receipt asking for Paracetamol (in
    stock) and far more Amoxicillin than exists. "Full lines only" means the
    Paracetamol sells and the Amoxicillin is skipped and reported."""
    conn = get_connection(DB_FILE)
    try:
        para = _medicine_id(conn, "Paracetamol")
        amox = _medicine_id(conn, "Amoxicillin")

        print("BEFORE:")
        _show(conn, para, "  Paracetamol")
        _show(conn, amox, "  Amoxicillin")

        # Ask for 2 Paracetamol (fine) and 9999 Amoxicillin (only 8 in stock).
        sale_id, skipped = record_sale(conn, [(para, 2), (amox, 9999)])

        print()
        if sale_id is None:
            print("-> nothing could be sold")
        else:
            total = conn.execute(
                "SELECT SUM(quantity * unit_price) FROM sale_items WHERE sale_id = ?",
                (sale_id,),
            ).fetchone()[0]
            print(f"-> recorded receipt #{sale_id}, total (computed): {total}")
        for medicine_id, requested, available in skipped:
            name = _medicine_name(conn, medicine_id)
            print(f"-> skipped {name}: wanted {requested}, only {available} in stock")

        print("\nAFTER:")
        _show(conn, para, "  Paracetamol")   # sold: went down
        _show(conn, amox, "  Amoxicillin")   # skipped: untouched
    finally:
        conn.close()


if __name__ == "__main__":
    main()
