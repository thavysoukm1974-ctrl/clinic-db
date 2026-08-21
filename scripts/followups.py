"""
followups.py -- "schedule to come back".

    python scripts/followups.py

When a patient is given medicine to take over time, the clinic wants to check on
them around when it RUNS OUT (for example to give the rest of a course), not on a
fixed date. So a follow-up stores the facts the run-out depends on -- how much
was given, the daily dose, the start date -- and the expected run-out date is
COMPUTED from them. The check-in list is the open follow-ups that should already
have run out.
"""

import math
from datetime import date, timedelta

from init_db import DB_FILE, get_connection


def expected_run_out(quantity_given, daily_dose, start_date):
    """Estimate the ISO date the medicine runs out, assuming the patient takes
    `daily_dose` units per day from `start_date`.

    days of supply = quantity_given / daily_dose, rounded UP so we don't check in
    too early (e.g. 10 tablets at 2/day = 5 days). This is only an estimate --
    "if taken correctly".
    """
    days = math.ceil(quantity_given / daily_dose)
    return (date.fromisoformat(start_date) + timedelta(days=days)).isoformat()


def add_follow_up(conn, patient_id, medicine_id, quantity_given, daily_dose,
                  start_date=None, visit_id=None, note=None):
    """Create an open follow-up. Returns (follow_up_id, expected_run_out_date).

    We store the facts (quantity, dose, start) and NOT a fixed return date, so
    the run-out estimate is always derived and stays consistent with them.
    """
    if quantity_given <= 0:
        raise ValueError("quantity_given must be positive")
    if daily_dose <= 0:
        raise ValueError("daily_dose must be positive")
    if start_date is None:
        start_date = date.today().isoformat()

    follow_up_id = conn.execute(
        """INSERT INTO follow_ups
               (patient_id, medicine_id, visit_id, quantity_given, daily_dose,
                start_date, status, note)
           VALUES (?, ?, ?, ?, ?, ?, 'open', ?)""",
        (patient_id, medicine_id, visit_id, quantity_given, daily_dose,
         start_date, note),
    ).lastrowid
    conn.commit()
    return follow_up_id, expected_run_out(quantity_given, daily_dose, start_date)


def open_follow_ups(conn, as_of=None):
    """Return ALL open follow-ups (due AND still-upcoming), soonest run-out first.

    Each row: (follow_up_id, patient_name, phone, medicine_name,
               expected_run_out, days_overdue), where days_overdue is
       (as_of - run_out) in days:  > 0 overdue by that many, 0 due today,
       < 0 that many days still to go.
    """
    if as_of is None:
        as_of = date.today().isoformat()
    as_of_date = date.fromisoformat(as_of)

    rows = conn.execute(
        """
        SELECT f.id, p.name, p.phone, m.name,
               f.quantity_given, f.daily_dose, f.start_date
        FROM follow_ups f
        JOIN patients p       ON p.id = f.patient_id
        LEFT JOIN medicines m ON m.id = f.medicine_id
        WHERE f.status = 'open'
        """
    ).fetchall()

    result = []
    for fid, patient, phone, medicine, quantity, dose, start in rows:
        run_out = expected_run_out(quantity, dose, start)
        days_overdue = (as_of_date - date.fromisoformat(run_out)).days
        result.append((fid, patient, phone, medicine, run_out, days_overdue))
    result.sort(key=lambda row: row[4])   # soonest run-out first
    return result


def due_follow_ups(conn, as_of=None):
    """Return only the follow-ups that are DUE now (medicine should have run out
    by `as_of`) -- the patients to actually call. A filter of open_follow_ups.
    """
    return [row for row in open_follow_ups(conn, as_of) if row[5] >= 0]


def close_follow_up(conn, follow_up_id, note=None):
    """Mark a follow-up done (the patient returned or was contacted)."""
    conn.execute(
        "UPDATE follow_ups SET status = 'closed', note = COALESCE(?, note) WHERE id = ?",
        (note, follow_up_id),
    )
    conn.commit()


def _patient_id(conn, name):
    return conn.execute("SELECT id FROM patients WHERE name = ?", (name,)).fetchone()[0]


def _medicine_id(conn, name):
    return conn.execute("SELECT id FROM medicines WHERE name = ?", (name,)).fetchone()[0]


def _print_due(conn, as_of, label):
    print(label)
    rows = due_follow_ups(conn, as_of=as_of)
    if not rows:
        print("  (nobody due)")
    for fid, patient, phone, medicine, run_out, days_overdue in rows:
        print(f"  #{fid} {patient} ({phone}) -- {medicine} ran out {run_out} "
              f"({days_overdue} days ago) -> call to check in")


def main():
    """Demonstration: one patient still has supply, one has already run out."""
    conn = get_connection(DB_FILE)
    try:
        today = date.today()
        dara = _patient_id(conn, "Dara Chan")
        sok = _patient_id(conn, "Sok Vann")
        para = _medicine_id(conn, "Paracetamol")
        amox = _medicine_id(conn, "Amoxicillin")

        # Dara: given 10 today at 2/day -> lasts ~5 days -> NOT due yet.
        _, dara_runout = add_follow_up(conn, dara, para, quantity_given=10,
                                       daily_dose=2, start_date=today.isoformat())
        # Sok: given 6, 2/day, but started 5 days ago -> ran out ~2 days ago -> DUE.
        started = (today - timedelta(days=5)).isoformat()
        _, sok_runout = add_follow_up(conn, sok, amox, quantity_given=6,
                                      daily_dose=2, start_date=started)

        print(f"Dara's supply should run out on {dara_runout}")
        print(f"Sok's supply should have run out on {sok_runout}\n")

        _print_due(conn, today.isoformat(), "Patients due for a check-in TODAY:")

        # Sok returns / is contacted -> close his follow-up.
        due_today = due_follow_ups(conn, as_of=today.isoformat())
        if due_today:
            close_follow_up(conn, due_today[0][0], note="called, coming in tomorrow")
            print("\n(after closing Sok's follow-up)")
            _print_due(conn, today.isoformat(), "Patients due for a check-in TODAY:")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
