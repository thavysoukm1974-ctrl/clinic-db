"""
sample_data.py -- fill the database with FAKE data so the tables can be tested.

    python scripts/sample_data.py

IMPORTANT: this is pretend data only -- never put real patient or sales data in
the test database. It exists so the tables can be seen working -- run a report,
check an expiring batch, look at a patient's visit history -- without touching
any real records.

Safe to run more than once, but it ADDS a fresh set each time (you'll get
duplicates). To start clean: delete db/clinic.sqlite and run init_db.py again.

The seeded sales are recorded with the REAL selling logic (sales.record_sale /
visits.record_visit), so they behave exactly like a real sale: stock is taken
from batches soonest-expiry-first, and each line records which batch it came
from. That is what lets the profit report work on this sample data.
"""

from datetime import date, timedelta

from init_db import DB_FILE, get_connection
from sales import record_sale
from visits import record_visit


def insert_suppliers(conn):
    """Add suppliers and return their ids keyed by name. The same medicine can be
    bought from more than one of these, at different prices."""
    rows = [
        # (name, phone, note)
        ("Pharma Co Ltd",   "023-000-000", "main wholesaler, buys in bulk"),
        ("Neighbor Clinic", "023-111-111", "small top-up buys nearby"),
    ]
    ids = {}
    for name, phone, note in rows:
        cur = conn.execute(
            "INSERT INTO suppliers (name, phone, note) VALUES (?, ?, ?)",
            (name, phone, note),
        )
        ids[name] = cur.lastrowid
    return ids


def insert_medicines(conn):
    """Add products to the catalog. Returns their new ids keyed by name.

    Note `unit` (how we COUNT it) vs `strength` (label dose, optional):
    the syrup's unit is 'bottle', the tablets' unit is 'tablet'.
    """
    rows = [
        # (name, form, unit, strength, category, unit_price, reorder_threshold, allow_partial_sale)
        ("Paracetamol", "tablet",  "tablet", "500mg",     "painkiller",  5.00, 20, 1),
        ("Amoxicillin", "capsule", "capsule","250mg",     "antibiotic", 12.00, 10, 0),  # example flagged no-partial (owner's medical call)
        ("Cough Syrup", "syrup",   "bottle", "125mg/5ml", "cold & flu",  8.50,  5, 1),
        ("Vitamin C",   "tablet",  "tablet", "1000mg",    "vitamin",     3.00, 15, 1),
        ("Gauze Bandage","dressing","roll",   None,       "supplies",    2.00, 10, 1),  # no strength -> fine
    ]
    ids = {}
    for name, form, unit, strength, category, price, threshold, allow_partial in rows:
        cur = conn.execute(
            """INSERT INTO medicines
                   (name, form, unit, strength, category, unit_price,
                    reorder_threshold, allow_partial_sale)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (name, form, unit, strength, category, price, threshold, allow_partial),
        )
        ids[name] = cur.lastrowid  # the id SQLite just assigned
    return ids


def insert_batches(conn, med_ids, sup_ids):
    """Add stock lots. received_quantity is set equal to quantity here because
    these are freshly received (nothing sold yet). Paracetamol gets TWO batches
    bought from different suppliers at different prices, to show that the same
    medicine can cost different amounts to restock."""
    today = date.today()
    expired = today - timedelta(days=10)         # expired 10 days ago
    expired_received = today - timedelta(days=40)  # ...and was received before that
    near = today + timedelta(days=30)            # expires soon -> FEFO sells first
    soon = today + timedelta(days=20)            # ~3 weeks out -> expiry warning
    later = today + timedelta(days=400)          # safely far away

    pharma = sup_ids["Pharma Co Ltd"]
    neighbor = sup_ids["Neighbor Clinic"]

    rows = [
        # (medicine, quantity, purchase_price, received_date, expiry_date, supplier_id)
        ("Paracetamol",   40, 3.50, today.isoformat(),            near.isoformat(),    neighbor),  # small top-up, pricier
        ("Paracetamol",  100, 3.00, today.isoformat(),            later.isoformat(),   pharma),    # bulk, cheaper
        ("Amoxicillin",    8, 8.00, today.isoformat(),            soon.isoformat(),    pharma),
        ("Cough Syrup",   30, 5.50, today.isoformat(),            later.isoformat(),   pharma),
        ("Cough Syrup",    3, 5.50, expired_received.isoformat(), expired.isoformat(), pharma),    # an expired lot still on hand
        ("Vitamin C",    200, 1.50, today.isoformat(),            later.isoformat(),   pharma),
        ("Gauze Bandage", 50, 1.00, today.isoformat(),            later.isoformat(),   pharma),
    ]
    for name, qty, cost, received, expiry, supplier_id in rows:
        conn.execute(
            """INSERT INTO batches
                   (medicine_id, supplier_id, received_quantity, quantity,
                    purchase_price, received_date, expiry_date)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (med_ids[name], supplier_id, qty, qty, cost, received, expiry),
        )


def insert_people(conn):
    """Add a couple of patients and staff. Returns (patient_ids, employee_ids)."""
    patients = [
        # (name, date_of_birth, sex, address, phone)
        ("Dara Chan",  "1990-05-12", "F", "12 Market St", "011-111-111"),
        ("Sok Vann",   "1975-11-03", "M", "5 River Rd",   "011-222-222"),
    ]
    patient_ids = {}
    for name, dob, sex, address, phone in patients:
        cur = conn.execute(
            "INSERT INTO patients (name, date_of_birth, sex, address, phone) VALUES (?, ?, ?, ?, ?)",
            (name, dob, sex, address, phone),
        )
        patient_ids[name] = cur.lastrowid

    employees = [
        # (name, role, date_of_birth, address, phone)
        ("Dr. Lin",   "doctor",   "1980-02-20", "9 Clinic Ave", "012-333-333"),
        ("Nurse Ary", "nurse",    "1992-07-01", "3 Hillside",   "012-444-444"),
        ("Pharm Bo",  "pharmacy", "1988-09-15", "7 Center Rd",  "012-555-555"),
    ]
    employee_ids = {}
    for name, role, dob, address, phone in employees:
        cur = conn.execute(
            "INSERT INTO employees (name, role, date_of_birth, address, phone) VALUES (?, ?, ?, ?, ?)",
            (name, role, dob, address, phone),
        )
        employee_ids[name] = cur.lastrowid

    return patient_ids, employee_ids


def main():
    conn = get_connection(DB_FILE)
    try:
        # --- catalog and stock -------------------------------------------------
        sup_ids = insert_suppliers(conn)
        med_ids = insert_medicines(conn)
        insert_batches(conn, med_ids, sup_ids)
        patient_ids, employee_ids = insert_people(conn)
        conn.commit()

        # --- some real sales, using the actual selling logic -------------------
        # A walk-in counter sale (no visit), sold by the pharmacy staff.
        record_sale(conn, [(med_ids["Paracetamol"], 2), (med_ids["Vitamin C"], 1)],
                    employee_id=employee_ids["Pharm Bo"])

        # A visit where medicine is given (recorded as a visit-linked sale).
        record_visit(
            conn, patient_ids["Dara Chan"], employee_id=employee_ids["Dr. Lin"],
            diagnosis="Fever", treatment="Rest and paracetamol",
            medicines=[(med_ids["Paracetamol"], 10)],
        )
        # A visit where nothing is given (proves a visit need not have a sale).
        record_visit(
            conn, patient_ids["Sok Vann"], employee_id=employee_ids["Dr. Lin"],
            diagnosis="Headache", treatment="Advised rest; medicine out of stock",
        )
    finally:
        conn.close()

    print("Sample data inserted. Open db/clinic.sqlite in DBeaver to look around.")


if __name__ == "__main__":
    main()
