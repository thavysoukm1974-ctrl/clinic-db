"""
stock.py -- read-only questions about how much stock we have.

    python scripts/stock.py

Everything here only READS the database -- it changes nothing, so it is
completely safe to run.

The key idea: a medicine's "stock on hand" is not stored as one number. It is
the SUM of the quantities of all its batches, added up on demand. Selling
(see sales.py) relies on the batch ordering that batches_for() produces below.
"""

from datetime import date

from init_db import DB_FILE, get_connection


def current_stock(conn):
    """Return a list of (medicine_id, name, unit, on_hand) -- one row per active
    medicine, with on_hand = total USABLE units (in stock and NOT expired).

    Expired units are left out because this number answers "how many can we
    sell?", and expired medicine is unsellable. A medicine whose only stock is
    expired therefore shows 0 here (and will then show up in low_stock).

    Read the SQL slowly; each line does one job:

      LEFT JOIN batches ... ON (not expired) -- attach only the USABLE batches.
                               Keeping the expiry test in the JOIN (not in WHERE)
                               means a medicine with NO usable batches still
                               appears, showing 0, instead of vanishing.
      SUM(b.quantity)       -- add up the usable units.
      COALESCE(..., 0)      -- no usable batches -> 0 instead of NULL.
      GROUP BY m.id         -- one row per medicine (makes SUM sum per medicine).
      WHERE m.is_active = 1 -- ignore discontinued medicines.
      ORDER BY m.name       -- show them alphabetically.
    """
    today = date.today().isoformat()
    rows = conn.execute(
        """
        SELECT m.id,
               m.name,
               m.unit,
               COALESCE(SUM(b.quantity), 0) AS on_hand
        FROM medicines m
        LEFT JOIN batches b
               ON b.medicine_id = m.id
              AND b.quantity > 0
              AND (b.expiry_date IS NULL OR b.expiry_date >= ?)
        WHERE m.is_active = 1
        GROUP BY m.id
        ORDER BY m.name
        """,
        (today,),
    ).fetchall()
    return rows


def batches_for(conn, medicine_id):
    """Return a medicine's SELLABLE batches, SOONEST-EXPIRY FIRST.

    "Sellable" means both in stock AND not expired -- expired medicine is
    physically on the shelf but must never be sold, so it is excluded here.
    This is the FEFO list -- "First Expiry, First Out". Selling walks it from the
    top, using the good stock closest to expiring first. Only reads; never sells.

      quantity > 0                        -- skip empty batches.
      expiry_date IS NULL OR >= today     -- keep only stock not past its expiry
                                             (NULL expiry = does not expire).
      ORDER BY expiry_date                -- soonest (good) expiry first.
    """
    today = date.today().isoformat()
    return conn.execute(
        """
        SELECT id, quantity, expiry_date, received_date
        FROM batches
        WHERE medicine_id = ?
          AND quantity > 0
          AND (expiry_date IS NULL OR expiry_date >= ?)
        ORDER BY expiry_date ASC
        """,
        (medicine_id, today),
    ).fetchall()


def main():
    conn = get_connection(DB_FILE)
    try:
        rows = current_stock(conn)

        print("Current stock on hand")
        print("-" * 40)
        para_id = None
        for med_id, name, unit, on_hand in rows:
            unit_label = unit if unit else "units"
            print(f"{name:<22} {on_hand:>5} {unit_label}")
            if name == "Paracetamol":
                para_id = med_id  # remember it, to demo the batch view below

        # Show the FEFO list the database would sell Paracetamol from.
        if para_id is not None:
            print("\nParacetamol batches, in the order we'd sell them (FEFO)")
            print("-" * 55)
            print(f"{'batch id':>8}  {'qty':>4}  expiry")
            for batch_id, qty, expiry, _received in batches_for(conn, para_id):
                print(f"{batch_id:>8}  {qty:>4}  {expiry}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
