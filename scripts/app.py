"""
app.py -- a simple TEXT menu for the clinic system (the first user interface).

    python scripts/app.py

This is the whole idea of a user interface, in its simplest form:
    show a menu  ->  read the user's choice  ->  call a function  ->  show result.

It does NOT contain any business logic of its own. Every choice just calls a
function we already built and tested in the other files (stock, sales, alerts,
visits, reports, followups). The menu is a thin layer on top of that logic --
the exact same logic a graphical window would call later.
"""

from datetime import date

from init_db import DB_FILE, get_connection, ensure_database
from stock import current_stock
from sales import record_sale
from alerts import expiring_soon, low_stock
from visits import patient_history
from followups import due_follow_ups
from reports import sales_summary, financial_summary, reorder_spend


# --- small input helpers -----------------------------------------------------

def _ask(prompt):
    """Read a line of input, trimmed of spaces."""
    return input(prompt).strip()


def _ask_positive_int(prompt):
    """Ask for a whole number greater than 0; return it, or None if invalid."""
    text = _ask(prompt)
    if text.isdigit() and int(text) > 0:
        return int(text)
    print("  (please type a whole number greater than 0)")
    return None


def _pick_from(conn, sql, header):
    """Print a numbered list of rows from `sql` and let the user pick one.
    Each row must start with (id, name, ...). Returns the chosen (id, name) or None.
    """
    rows = conn.execute(sql).fetchall()
    if not rows:
        print("  (nothing to choose from)")
        return None
    print(header)
    for number, row in enumerate(rows, start=1):
        print(f"  {number}) {row[1]}")
    choice = _ask("  pick a number (blank to cancel): ")
    if choice.isdigit() and 1 <= int(choice) <= len(rows):
        chosen = rows[int(choice) - 1]
        return chosen[0], chosen[1]      # (id, name)
    return None


# --- one function per menu action --------------------------------------------
# Each takes the open connection and prints something. This is where the menu
# meets the logic we built earlier.

def do_view_stock(conn):
    print("\nCurrent stock on hand (usable units):")
    for _id, name, unit, on_hand, _threshold in current_stock(conn):
        print(f"  {name:<18} {on_hand:>5} {unit or 'units'}")


def do_view_alerts(conn):
    print("\nExpiring soon (within 30 days, incl. already expired):")
    rows = expiring_soon(conn, days=30)
    if not rows:
        print("  (nothing)")
    for name, batch_id, quantity, expiry, days_left in rows:
        when = f"EXPIRED {-days_left}d ago" if days_left < 0 else f"in {days_left}d"
        print(f"  {name:<18} {quantity:>4} units, {expiry} ({when})")

    print("\nLow on stock (at or below reorder level):")
    rows = low_stock(conn)
    if not rows:
        print("  (nothing)")
    for name, on_hand, threshold in rows:
        print(f"  {name:<18} {on_hand} left (reorder at {threshold})")


def do_record_sale(conn):
    # Build the basket one medicine at a time, then hand it to record_sale.
    print("\nRecord a sale. Add medicines one by one.")
    medicines = conn.execute(
        "SELECT id, name, unit_price FROM medicines WHERE is_active = 1 ORDER BY name"
    ).fetchall()
    names = {mid: name for mid, name, _price in medicines}

    print("Medicines:")
    for number, (mid, name, price) in enumerate(medicines, start=1):
        print(f"  {number}) {name} @ {price}")

    items = []
    while True:
        choice = _ask("Add medicine number (blank to finish): ")
        if choice == "":
            break
        if not (choice.isdigit() and 1 <= int(choice) <= len(medicines)):
            print("  (not a valid medicine number)")
            continue
        medicine_id = medicines[int(choice) - 1][0]
        quantity = _ask_positive_int("  quantity: ")
        if quantity is None:
            continue
        items.append((medicine_id, quantity))
        print(f"  added {quantity} x {names[medicine_id]}")

    if not items:
        print("Nothing added -- sale cancelled.")
        return

    sale_id, shortfalls = record_sale(conn, items)
    if sale_id is None:
        print("Nothing could be sold (all items were out of stock).")
    else:
        total = conn.execute(
            "SELECT SUM(quantity * unit_price) FROM sale_items WHERE sale_id = ?",
            (sale_id,),
        ).fetchone()[0]
        print(f"Recorded sale #{sale_id}. Total: {total}")
    for medicine_id, requested, sold in shortfalls:
        if sold == 0:
            print(f"  note: {names[medicine_id]} not sold (wanted {requested}, out of stock)")
        else:
            print(f"  note: {names[medicine_id]} only {sold} sold of {requested} wanted")


def do_patient_history(conn):
    picked = _pick_from(
        conn, "SELECT id, name FROM patients ORDER BY name", "\nPatients:"
    )
    if picked is None:
        return
    patient_id, name = picked
    print(f"\n{name} -- visit history (newest first):")
    history = patient_history(conn, patient_id)
    if not history:
        print("  (no visits)")
    for _vid, vdate, diagnosis, _treatment, doctor, medicines in history:
        print(f"  [{vdate}] {diagnosis}  (seen by {doctor or 'unknown'})")
        for mname, qty, price in medicines:
            print(f"           given: {qty} x {mname} @ {price}")


def do_follow_ups(conn):
    print("\nPatients due for a check-in (given medicine should have run out):")
    rows = due_follow_ups(conn)
    if not rows:
        print("  (nobody due)")
    for _fid, patient, phone, medicine, run_out, days_overdue in rows:
        print(f"  {patient} ({phone}) -- {medicine} ran out {run_out} "
              f"({days_overdue}d ago)")


def do_money_report(conn):
    today = date.today()
    start = today.replace(day=1).isoformat()
    end = today.isoformat()

    num_sales, revenue = sales_summary(conn, start, end)
    _rev, cogs, profit = financial_summary(conn, start, end)
    spend = reorder_spend(conn, start, end)

    print(f"\nMoney this month ({start} to {end}):")
    print(f"  sales:        {num_sales}")
    print(f"  revenue:      {revenue}")
    print(f"  cost of sold: {cogs}")
    print(f"  gross profit: {profit}")
    print(f"  reorder spend:{spend}")


# --- the menu itself ---------------------------------------------------------
# One place lists every choice: the number, the label shown, and the function to
# run. The menu is printed from this same list, so it can never drift out of sync.

MENU = [
    ("1", "View current stock", do_view_stock),
    ("2", "View alerts (expiring / low stock)", do_view_alerts),
    ("3", "Record a sale", do_record_sale),
    ("4", "Patient visit history", do_patient_history),
    ("5", "Follow-ups due", do_follow_ups),
    ("6", "Money report (this month)", do_money_report),
]


def print_menu():
    print("\n===== Clinic system =====")
    for key, label, _action in MENU:
        print(f"  {key}. {label}")
    print("  0. Quit")


def main():
    ensure_database()   # first run on a new machine: create the empty database
    actions = {key: action for key, _label, action in MENU}
    conn = get_connection(DB_FILE)
    try:
        while True:
            print_menu()
            choice = _ask("Choose: ")
            if choice == "0":
                break
            action = actions.get(choice)
            if action is None:
                print("  (unknown choice)")
            else:
                action(conn)
    finally:
        conn.close()
    print("Goodbye.")


if __name__ == "__main__":
    main()
