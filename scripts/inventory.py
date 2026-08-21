"""
inventory.py -- ADD new catalog and stock records (data entry for the shop).

    python scripts/inventory.py   (runs a small self-test)

These are the CREATE operations that let a clinic enter its OWN medicines and
stock through the app, instead of anything being hardcoded -- so a second clinic
could start from an empty database and fill it in themselves. (Reading stock is
in stock.py; selling is in sales.py; here we only ADD.)
"""

from datetime import date

from init_db import DB_FILE, get_connection

# Common values offered as dropdown SUGGESTIONS in the add-medicine form. They
# are suggestions only -- the fields still accept any text a clinic types, so a
# medicine form or unit we didn't list can still be entered.
COMMON_FORMS = ("tablet", "capsule", "syrup", "cream", "ointment",
                "drops", "injection", "sachet", "dressing")
COMMON_UNITS = ("tablet", "capsule", "bottle", "box", "strip",
                "tube", "roll", "sachet", "piece")


def add_medicine(conn, name, form=None, unit=None, strength=None, category=None,
                 unit_price=0.0, reorder_threshold=0, allow_partial_sale=1):
    """Add a medicine to the catalog. Returns its new id.

    Only `name` is required; everything else has a sensible default so a quick
    entry is possible and details can be filled in later.
    """
    if not name or not name.strip():
        raise ValueError("a medicine needs a name")
    medicine_id = conn.execute(
        """INSERT INTO medicines
               (name, form, unit, strength, category, unit_price,
                reorder_threshold, allow_partial_sale)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (name.strip(), form, unit, strength, category, unit_price,
         reorder_threshold, allow_partial_sale),
    ).lastrowid
    conn.commit()
    return medicine_id


def add_supplier(conn, name, phone=None, note=None):
    """Add a supplier. Returns its new id."""
    if not name or not name.strip():
        raise ValueError("a supplier needs a name")
    supplier_id = conn.execute(
        "INSERT INTO suppliers (name, phone, note) VALUES (?, ?, ?)",
        (name.strip(), phone, note),
    ).lastrowid
    conn.commit()
    return supplier_id


def receive_stock(conn, medicine_id, quantity, purchase_price=None,
                  expiry_date=None, received_date=None, supplier_id=None):
    """Record a newly received batch (lot) of a medicine, and return its id.

    received_quantity and quantity both start equal to `quantity` because
    nothing has been sold from this lot yet. Selling later lowers quantity but
    never received_quantity, so we can always tell how much was originally bought.
    """
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    if received_date is None:
        received_date = date.today().isoformat()
    batch_id = conn.execute(
        """INSERT INTO batches
               (medicine_id, supplier_id, received_quantity, quantity,
                purchase_price, received_date, expiry_date)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (medicine_id, supplier_id, quantity, quantity,
         purchase_price, received_date, expiry_date),
    ).lastrowid
    conn.commit()
    return batch_id


def main():
    """Self-test on the sample database: add a medicine, a supplier, and a batch."""
    from stock import current_stock
    conn = get_connection(DB_FILE)
    try:
        medicine_id = add_medicine(conn, "Ibuprofen", form="tablet", unit="tablet",
                                   strength="200mg", category="painkiller",
                                   unit_price=6.0, reorder_threshold=10)
        supplier_id = add_supplier(conn, "Test Supplier")
        receive_stock(conn, medicine_id, quantity=50, purchase_price=2.5,
                      expiry_date="2027-01-01", supplier_id=supplier_id)
        print("Added Ibuprofen with a batch of 50. Current stock:")
        for _id, name, unit, on_hand, _threshold in current_stock(conn):
            print(f"  {name:<16} {on_hand} {unit or ''}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
