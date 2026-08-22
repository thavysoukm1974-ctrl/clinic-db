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


def record_sale(conn, items, visit_id=None, paid=True, patient_id=None):
    """Record ONE sale (a receipt) that may contain several medicines.

    `items` is a list, one entry per medicine on the receipt, each either:
        (medicine_id, quantity)              -- sold at the medicine's current price
        (medicine_id, quantity, unit_price)  -- sold at THIS price instead
    The override lets a line be free (price 0) or discounted. Whatever price is
    used is frozen onto the sale, so a later catalog price change never rewrites it.

    paid=False records the sale as MONEY OWED (pay later). A pay-later sale MUST
    be tied to a real patient so the debt is always attributable: either through
    visit_id (a visit knows its patient) or through patient_id (a counter credit
    sale). Recording an unpaid sale with neither is refused.
    See outstanding_debts() and mark_sale_paid().

    Policy when a medicine is short on stock depends on that medicine's own
    `allow_partial_sale` flag (a column on the medicines table):
      * flag = 0 (default): sell all-or-none of the line -- if it can't be filled
        completely, leave it off the sale entirely.
      * flag = 1: sell whatever IS in stock (a partial amount).
    Either way, the OTHER medicines on the receipt that can be filled still sell.
    Every line that did not fully fill is reported back so the seller can tell
    the customer.

    Returns a pair (sale_id, shortfalls):
      * sale_id -- the new sale's id, or None if nothing at all could be sold,
      * shortfalls -- a list of (medicine_id, requested, sold) for lines that did
        NOT fully fill. sold = 0 means the line was left off; 0 < sold < requested
        means it was sold partially.

    This is separate from transactional safety: whatever sale we DO make is still
    all-or-nothing at the database level (one commit at the end), so stock can
    never go down without the matching sale. The flag only decides WHICH medicines
    (and how many) end up on the receipt.
    """
    if not items:
        raise ValueError("a sale needs at least one item")
    # A debt must belong to a real patient, so we can always tell who owes.
    if not paid and visit_id is None and patient_id is None:
        raise ValueError("a pay-later sale must be linked to a patient")

    # Normalize every item to (medicine_id, quantity, unit_price), where a
    # unit_price of None means "use the medicine's current catalog price".
    lines = []
    for item in items:
        if len(item) == 3:
            medicine_id, quantity, unit_price = item
        else:
            medicine_id, quantity = item
            unit_price = None
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        lines.append((medicine_id, quantity, unit_price))

    # 1. Decide how much of each medicine to sell (carrying each line's price).
    #    (Assumes each medicine appears at most once on the receipt; if the same
    #     medicine is bought twice, combine it into one line first.)
    to_sell = []     # (medicine_id, quantity_to_sell, unit_price) we will sell
    shortfalls = []  # (medicine_id, requested, sold) for lines not fully filled
    for medicine_id, quantity, unit_price in lines:
        available = sum(qty for (_id, qty, _exp, _rec) in batches_for(conn, medicine_id))

        if quantity <= available:
            to_sell.append((medicine_id, quantity, unit_price))     # full line
        elif _allows_partial(conn, medicine_id) and available > 0:
            to_sell.append((medicine_id, available, unit_price))    # sell what's left ...
            shortfalls.append((medicine_id, quantity, available))   # ... and note the shortfall
        else:
            shortfalls.append((medicine_id, quantity, 0))           # left off entirely

    # 2. If not a single medicine can be sold, don't create an empty sale.
    if not to_sell:
        return None, shortfalls

    # 3. One sale header for the medicines we can fill (NULL visit_id = walk-in).
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sale_id = conn.execute(
        "INSERT INTO sales (sale_datetime, visit_id, paid, patient_id) VALUES (?, ?, ?, ?)",
        (now, visit_id, 1 if paid else 0, patient_id),
    ).lastrowid

    # 4. Fill each sellable line from its batches (soonest-expiry first).
    for medicine_id, quantity, unit_price in to_sell:
        _fill_one_line(conn, sale_id, medicine_id, quantity, unit_price)

    # 5. One commit makes the whole (fillable) sale permanent at once.
    conn.commit()
    return sale_id, shortfalls


def _fill_one_line(conn, sale_id, medicine_id, quantity, unit_price=None):
    """Take `quantity` units of ONE medicine and add it to an existing sale.

    Walk the medicine's batches soonest-expiry-first (FEFO): take units from each
    batch in turn, record which batch they came from, freeze the price, and
    subtract the stock. If one batch runs short, continue into the next batch.
    The caller has already checked there is enough stock and created the sale.

    `unit_price` is the price to charge per unit. If it is None, the medicine's
    current catalog price is used. A value of 0 is a real price (a free giveaway),
    which is why we test for None, not for "falsy".
    """
    # Fill in the catalog price only when no explicit price was given (0 stays 0).
    if unit_price is None:
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


def _allows_partial(conn, medicine_id):
    """True if this medicine may be sold in a smaller amount than asked when
    stock is short (its allow_partial_sale flag is 1)."""
    row = conn.execute(
        "SELECT allow_partial_sale FROM medicines WHERE id = ?", (medicine_id,)
    ).fetchone()
    return bool(row[0])


def outstanding_debts(conn):
    """Return the unpaid sales (money owed), oldest first. Each row is
    (sale_id, sale_datetime, who, amount).

    `who` is the patient who owes -- found either through the sale's visit or
    directly on the sale (both point at the patients table). `amount` is the
    sale's total, computed from its lines. Debts always have a patient.
    """
    return conn.execute(
        """
        SELECT s.id,
               s.sale_datetime,
               COALESCE(pv.name, pd.name, '?') AS who,
               COALESCE(SUM(si.quantity * si.unit_price), 0) AS amount
        FROM sales s
        JOIN sale_items si     ON si.sale_id = s.id
        LEFT JOIN visits v     ON v.id = s.visit_id
        LEFT JOIN patients pv  ON pv.id = v.patient_id
        LEFT JOIN patients pd  ON pd.id = s.patient_id
        WHERE s.paid = 0
        GROUP BY s.id
        ORDER BY s.sale_datetime
        """
    ).fetchall()


def mark_sale_paid(conn, sale_id):
    """Mark a previously-owed sale as now paid."""
    conn.execute("UPDATE sales SET paid = 1 WHERE id = ?", (sale_id,))
    conn.commit()


def _medicine_name(conn, medicine_id):
    """Look up a medicine's name (used only for clear messages)."""
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
    """Demonstration on the sample data: one receipt that hits all three cases:
      * Paracetamol 2  -> in stock, sells fully.
      * Amoxicillin 9999 -> short, flag = 0 (antibiotic) -> sold none, left off.
      * Vitamin C 9999   -> short, flag = 1 -> sells what's left (partial).
    """
    conn = get_connection(DB_FILE)
    try:
        para = _medicine_id(conn, "Paracetamol")
        amox = _medicine_id(conn, "Amoxicillin")
        vitc = _medicine_id(conn, "Vitamin C")

        print("BEFORE:")
        for mid, name in [(para, "Paracetamol"), (amox, "Amoxicillin"), (vitc, "Vitamin C")]:
            _show(conn, mid, f"  {name} (partial allowed: {_allows_partial(conn, mid)})")

        sale_id, shortfalls = record_sale(conn, [(para, 2), (amox, 9999), (vitc, 9999)])

        print()
        if sale_id is None:
            print("-> nothing could be sold")
        else:
            total = conn.execute(
                "SELECT SUM(quantity * unit_price) FROM sale_items WHERE sale_id = ?",
                (sale_id,),
            ).fetchone()[0]
            print(f"-> recorded receipt #{sale_id}, total (computed): {total}")
        for medicine_id, requested, sold in shortfalls:
            name = _medicine_name(conn, medicine_id)
            if sold == 0:
                print(f"-> {name}: wanted {requested}, sold NONE (partial not allowed)")
            else:
                print(f"-> {name}: wanted {requested}, sold {sold} (partial)")

        print("\nAFTER:")
        for mid, name in [(para, "Paracetamol"), (amox, "Amoxicillin"), (vitc, "Vitamin C")]:
            _show(conn, mid, f"  {name}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
