"""
sample_data.py -- fill the database with FAKE data so we can test and learn.

    python scripts/sample_data.py

IMPORTANT: this is pretend data only -- never put real patient or sales data in
the test database. It exists so the tables can be seen working -- run a report,
check an expiring batch, look at a patient's visit history -- without touching
any real records.

Safe to run more than once, but it ADDS a fresh set each time (you'll get
duplicates). To start clean: delete db/clinic.sqlite and run init_db.py again.

Read this file to see, in plain Python, HOW rows get inserted -- especially:
  * a SALE = one row in `sales` + several rows in `sale_items`
  * a sale can be a walk-in (no visit) OR tied to a visit (medicine given
    during diagnosis -- which the clinic counts as selling)
  * a VISIT with no sale (a patient can be seen and buy nothing)
"""

from datetime import date, datetime, timedelta

# Reuse the exact same connection helper the rest of the project uses, so
# foreign keys are always ON. (init_db.py lives next to this file.)
from init_db import DB_FILE, get_connection


# ---------------------------------------------------------------- pharmacy side

def insert_medicines(conn):
    """Add products to the catalog. Returns their new ids keyed by name.

    Note `unit` (how we COUNT it) vs `strength` (label dose, optional):
    the syrup's unit is 'bottle', the tablets' unit is 'tablet'.
    """
    rows = [
        # (name, form, unit, strength, category, unit_price, reorder_threshold, allow_partial_sale)
        ("Paracetamol", "tablet",  "tablet", "500mg",     "painkiller",  5.00, 20, 1),
        ("Amoxicillin", "capsule", "capsule","250mg",     "antibiotic", 12.00, 10, 0),  # antibiotic: no partial course
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


def insert_batches(conn, med_ids):
    """Add stock lots. One batch expires SOON on purpose, so the 'expiring soon'
    warning has something to find, and Amoxicillin is left low on stock."""
    today = date.today()
    expired = today - timedelta(days=10)  # ALREADY expired 10 days ago
    near = today + timedelta(days=30)    # expires fairly soon -> FEFO sells this FIRST
    soon = today + timedelta(days=20)    # ~3 weeks out -> should trigger a warning
    later = today + timedelta(days=400)  # safely far away

    rows = [
        # (medicine name, quantity, purchase_price, received_date, expiry_date)
        ("Paracetamol",   40, 3.00, today.isoformat(), near.isoformat()),   # 2 Paracetamol batches,
        ("Paracetamol",  100, 3.00, today.isoformat(), later.isoformat()),  #   different expiry dates
        ("Amoxicillin",    8, 8.00, today.isoformat(), soon.isoformat()),   # low AND expiring
        ("Cough Syrup",   30, 5.50, today.isoformat(), later.isoformat()),
        ("Cough Syrup",    3, 5.50, today.isoformat(), expired.isoformat()),# an expired lot still on hand
        ("Vitamin C",    200, 1.50, today.isoformat(), later.isoformat()),
        ("Gauze Bandage", 50, 1.00, today.isoformat(), later.isoformat()),
    ]
    for name, qty, cost, received, expiry in rows:
        conn.execute(
            """INSERT INTO batches
                   (medicine_id, quantity, purchase_price, received_date, expiry_date)
               VALUES (?, ?, ?, ?, ?)""",
            (med_ids[name], qty, cost, received, expiry),
        )


def record_sale(conn, med_ids, lines, visit_id=None):
    """Insert ONE sale as test data (a simplified seeder, not the real selling
    logic -- the real one that also subtracts stock lives in sales.py).

    A sale is TWO steps:
      1. insert the receipt into `sales` -> gives a sale_id
         (visit_id is NULL for a walk-in counter sale, or set when the sale is
          medicine given during a visit)
      2. insert each line into `sale_items`, all pointing at that sale_id

    `lines` is a list of (medicine_name, quantity, unit_price).
    No total is stored -- it is computed from the lines when needed. This seeder
    intentionally does NOT decrement batch stock; it only fills in example rows.
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Step 1: the receipt (optionally tied to a visit).
    cur = conn.execute(
        "INSERT INTO sales (sale_datetime, visit_id) VALUES (?, ?)",
        (now, visit_id),
    )
    sale_id = cur.lastrowid

    # Step 2: the lines, each tied to sale_id.
    for name, qty, price in lines:
        conn.execute(
            """INSERT INTO sale_items (sale_id, medicine_id, quantity, unit_price)
               VALUES (?, ?, ?, ?)""",
            (sale_id, med_ids[name], qty, price),
        )
    return sale_id


# ---------------------------------------------------------------- clinical side

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


def insert_visits(conn, patient_ids, employee_ids, med_ids):
    """Two visits that show the key ideas:

      * Visit A: patient seen by a doctor, diagnosis + treatment recorded, and
        medicine given -- which counts as SELLING, so we record a sale LINKED to
        this visit (no separate prescription table).
      * Visit B: patient seen, but NOTHING given (stock was out) -- no sale.
        This proves a visit does not have to result in a sale.
    """
    today = date.today().isoformat()

    # Visit A -- medicine given during diagnosis = a sale tied to the visit.
    cur = conn.execute(
        """INSERT INTO visits (patient_id, employee_id, visit_date, diagnosis, treatment)
           VALUES (?, ?, ?, ?, ?)""",
        (patient_ids["Dara Chan"], employee_ids["Dr. Lin"], today,
         "Fever", "Rest and paracetamol"),
    )
    visit_a = cur.lastrowid
    record_sale(conn, med_ids, [("Paracetamol", 10, 5.00)], visit_id=visit_a)

    # Visit B -- seen, but nothing given (e.g. stock was out). No sale at all.
    conn.execute(
        """INSERT INTO visits (patient_id, employee_id, visit_date, diagnosis, treatment)
           VALUES (?, ?, ?, ?, ?)""",
        (patient_ids["Sok Vann"], employee_ids["Dr. Lin"], today,
         "Headache", "Advised rest; medicine out of stock"),
    )


def main():
    conn = get_connection(DB_FILE)
    try:
        med_ids = insert_medicines(conn)
        insert_batches(conn, med_ids)

        # A walk-in counter sale -- no visit attached (visit_id stays NULL).
        record_sale(conn, med_ids, [("Paracetamol", 2, 5.00), ("Vitamin C", 1, 3.00)])

        patient_ids, employee_ids = insert_people(conn)
        insert_visits(conn, patient_ids, employee_ids, med_ids)

        conn.commit()
    finally:
        conn.close()

    print("Sample data inserted. Open db/clinic.sqlite in DBeaver to look around.")


if __name__ == "__main__":
    main()
