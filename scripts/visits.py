"""
visits.py -- record a patient VISIT (the clinical side), optionally with the
medicine given during it, and read back a patient's visit history.

    python scripts/visits.py

A visit records that a patient was seen: the date, the doctor, and the diagnosis
and treatment for THAT visit (a patient returns many times, so these belong to
the visit, not the patient). Giving medicine during a visit counts as selling
it, so any medicine handed over is recorded as a sale linked to the visit --
which also subtracts stock -- and there is no separate prescription record.
"""

from datetime import datetime

from init_db import DB_FILE, get_connection
from sales import record_sale, _medicine_id


def add_patient(conn, name, date_of_birth=None, sex=None, address=None, phone=None):
    """Add a patient and return the new patient_id."""
    if not name or not name.strip():
        raise ValueError("a patient needs a name")
    patient_id = conn.execute(
        """INSERT INTO patients (name, date_of_birth, sex, address, phone)
           VALUES (?, ?, ?, ?, ?)""",
        (name.strip(), date_of_birth, sex, address, phone),
    ).lastrowid
    conn.commit()
    return patient_id


# The staff roles the clinic normally uses. Offered as SUGGESTIONS only -- role
# is stored as free text, so another clinic could enter a role not in this list.
COMMON_ROLES = ("doctor", "nurse", "pharmacy", "lab")


def add_employee(conn, name, role=None, date_of_birth=None, address=None, phone=None):
    """Add a staff member and return the new employee_id.

    Only `name` is required. `role` is free text (see COMMON_ROLES for the usual
    ones); date_of_birth is stored instead of age so it never goes stale.
    """
    if not name or not name.strip():
        raise ValueError("an employee needs a name")
    employee_id = conn.execute(
        """INSERT INTO employees (name, role, date_of_birth, address, phone)
           VALUES (?, ?, ?, ?, ?)""",
        (name.strip(), role, date_of_birth, address, phone),
    ).lastrowid
    conn.commit()
    return employee_id


def record_visit(conn, patient_id, employee_id=None, visit_date=None,
                 diagnosis=None, treatment=None, medicines=None, paid=True):
    """Record one visit, and optionally the medicine given during it.

    `medicines` (optional) is a list of items handed to the patient -- each
    (medicine_id, quantity) at catalog price, or (medicine_id, quantity, price)
    to override (price 0 = given free). Because giving medicine counts as selling
    it, it is recorded as a sale linked to this visit, which decrements stock.
    paid=False records that sale as owed (pay later); the debt is attributed to
    this visit's patient.

    Returns (visit_id, sale_id, shortfalls):
      * visit_id   -- the new visit (always created; a visit is valid on its own,
                      even if no medicine is given).
      * sale_id    -- the linked sale, or None if no medicine was given or none
                      of it could be filled.
      * shortfalls -- medicines that could not be fully given (from record_sale);
                      empty if none. Each is (medicine_id, requested, sold).
    """
    if visit_date is None:
        visit_date = datetime.now().strftime("%Y-%m-%d")   # default: today

    # The visit itself. Recorded (and committed) first, because a visit is a
    # valid record on its own -- the patient was seen whether or not medicine
    # was available to give.
    visit_id = conn.execute(
        """INSERT INTO visits (patient_id, employee_id, visit_date, diagnosis, treatment)
           VALUES (?, ?, ?, ?, ?)""",
        (patient_id, employee_id, visit_date, diagnosis, treatment),
    ).lastrowid
    conn.commit()

    sale_id = None
    shortfalls = []
    if medicines:
        # Same selling logic as a counter sale, tagged with this visit_id and
        # attributed to the doctor who saw the patient as the seller.
        sale_id, shortfalls = record_sale(conn, medicines, visit_id=visit_id,
                                          paid=paid, employee_id=employee_id)

    return visit_id, sale_id, shortfalls


def patient_history(conn, patient_id):
    """Return a patient's visits, NEWEST FIRST, each with the medicine given.

    For each visit we look up the medicine on its linked sale (if any) by joining
    that sale to its sale_items. A visit with no sale just has an empty medicine
    list. Returns a list of:
        (visit_id, visit_date, diagnosis, treatment, doctor_name, medicines)
    where medicines is a list of (medicine_name, quantity, unit_price).
    """
    visits = conn.execute(
        """
        SELECT v.id, v.visit_date, v.diagnosis, v.treatment, e.name
        FROM visits v
        LEFT JOIN employees e ON e.id = v.employee_id
        WHERE v.patient_id = ?
        ORDER BY v.visit_date DESC, v.id DESC
        """,
        (patient_id,),
    ).fetchall()

    history = []
    for visit_id, visit_date, diagnosis, treatment, doctor in visits:
        medicines = conn.execute(
            """
            SELECT m.name, si.quantity, si.unit_price
            FROM sales s
            JOIN sale_items si ON si.sale_id = s.id
            JOIN medicines m   ON m.id = si.medicine_id
            WHERE s.visit_id = ?
            ORDER BY m.name
            """,
            (visit_id,),
        ).fetchall()
        history.append((visit_id, visit_date, diagnosis, treatment, doctor, medicines))
    return history


def _patient_id(conn, name):
    return conn.execute("SELECT id FROM patients WHERE name = ?", (name,)).fetchone()[0]


def _employee_id(conn, name):
    return conn.execute("SELECT id FROM employees WHERE name = ?", (name,)).fetchone()[0]


def main():
    """Demonstration: record a new visit for an existing patient (giving some
    medicine), then print that patient's whole visit history."""
    conn = get_connection(DB_FILE)
    try:
        dara = _patient_id(conn, "Dara Chan")
        doctor = _employee_id(conn, "Dr. Lin")
        cough = _medicine_id(conn, "Cough Syrup")

        visit_id, sale_id, shortfalls = record_visit(
            conn, dara, employee_id=doctor,
            diagnosis="Cough", treatment="Cough syrup, rest",
            medicines=[(cough, 2)],
        )
        print(f"Recorded visit #{visit_id} "
              f"(linked sale #{sale_id}, shortfalls: {shortfalls})\n")

        print("Dara Chan -- visit history (newest first):")
        for vid, vdate, diag, treat, doctor_name, medicines in patient_history(conn, dara):
            seen_by = doctor_name if doctor_name else "unknown"
            print(f"  [{vdate}] visit #{vid}: {diag}  (seen by {seen_by})")
            print(f"           treatment: {treat}")
            if medicines:
                for mname, qty, price in medicines:
                    print(f"           given: {qty} x {mname} @ {price}")
            else:
                print("           given: (nothing)")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
