"""
sample_data.py -- fill the database with FAKE data so we can test and learn.

    python scripts/sample_data.py

IMPORTANT: this is pretend data (from the plan: "No real patient or sales data
in the test system"). It exists so you can see the tables working -- run a
report, check an expiring batch, look at a patient's visit history -- without
touching the clinic's real records.

Safe to run more than once, but it ADDS a fresh set each time (you'll get
duplicates). To start clean: delete db/clinic.sqlite and run init_db.py again.

Read this file to see, in plain Python, HOW rows get inserted -- especially:
  * a SALE = one row in `sales` + several rows in `sale_items`
  * a VISIT = one row in `visits` (+ optional `prescription_items`)
  * how a visit is NOT tied to a sale (a patient can be seen and buy nothing)
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
        # (name, form, unit, strength, category, unit_price, reorder_threshold)
        ("Paracetamol", "tablet",  "tablet", "500mg",     "painkiller",  5.00, 20),
        ("Amoxicillin", "capsule", "capsule","250mg",     "antibiotic", 12.00, 10),
        ("Cough Syrup", "syrup",   "bottle", "125mg/5ml", "cold & flu",  8.50,  5),
        ("Vitamin C",   "tablet",  "tablet", "1000mg",    "vitamin",     3.00, 15),
        ("Gauze Bandage","dressing","roll",   None,       "supplies",    2.00, 10),  # no strength -> fine
    ]
    ids = {}
    for name, form, unit, strength, category, price, threshold in rows:
        cur = conn.execute(
            """INSERT INTO medicines
                   (name, form, unit, strength, category, unit_price, reorder_threshold)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (name, form, unit, strength, category, price, threshold),
        )
        ids[name] = cur.lastrowid  # the id SQLite just assigned
    return ids


def insert_batches(conn, med_ids):
    """Add stock lots. One batch expires SOON on purpose, so the 'expiring soon'
    warning has something to find, and Amoxicillin is left low on stock."""
    today = date.today()
    soon = today + timedelta(days=20)    # ~3 weeks out -> should trigger a warning
    later = today + timedelta(days=400)  # safely far away

    rows = [
        # (medicine name, quantity, purchase_price, received_date, expiry_date)
        ("Paracetamol",  100, 3.00, today.isoformat(), later.isoformat()),
        ("Amoxicillin",    8, 8.00, today.isoformat(), soon.isoformat()),   # low AND expiring
        ("Cough Syrup",   30, 5.50, today.isoformat(), later.isoformat()),
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


def insert_one_sample_sale(conn, med_ids):
    """ONE example counter sale, to show the sales/sale_items relationship.

    A sale is TWO steps:
      1. insert the receipt into `sales`  -> gives us a sale_id
      2. insert each line into `sale_items`, all pointing at that sale_id
    There is NO total to store -- we compute it from the lines when needed.
    (Decrementing batch stock is deliberately NOT done here; that's logic we
    build together so you understand it fully.)
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Step 1: the receipt.
    cur = conn.execute("INSERT INTO sales (sale_datetime) VALUES (?)", (now,))
    sale_id = cur.lastrowid

    # Step 2: the lines -- (medicine name, quantity, unit_price), each tied to sale_id.
    lines = [
        ("Paracetamol", 2, 5.00),
        ("Vitamin C",   1, 3.00),
    ]
    for name, qty, price in lines:
        conn.execute(
            """INSERT INTO sale_items (sale_id, medicine_id, quantity, unit_price)
               VALUES (?, ?, ?, ?)""",
            (sale_id, med_ids[name], qty, price),
        )


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
        one medicine given (a prescription_item).
      * Visit B: patient seen, but NOTHING given -- no prescription, no sale.
        This proves a visit does not have to result in a sale.
    """
    today = date.today().isoformat()

    # Visit A -- with a medicine given.
    cur = conn.execute(
        """INSERT INTO visits (patient_id, employee_id, visit_date, diagnosis, treatment)
           VALUES (?, ?, ?, ?, ?)""",
        (patient_ids["Dara Chan"], employee_ids["Dr. Lin"], today,
         "Fever", "Rest and paracetamol"),
    )
    visit_a = cur.lastrowid
    conn.execute(
        "INSERT INTO prescription_items (visit_id, medicine_id, quantity) VALUES (?, ?, ?)",
        (visit_a, med_ids["Paracetamol"], 10),
    )

    # Visit B -- seen, but nothing given (e.g. stock was out). No prescription rows.
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
        insert_one_sample_sale(conn, med_ids)

        patient_ids, employee_ids = insert_people(conn)
        insert_visits(conn, patient_ids, employee_ids, med_ids)

        conn.commit()
    finally:
        conn.close()

    print("Sample data inserted. Open db/clinic.sqlite in DBeaver to look around.")


if __name__ == "__main__":
    main()
