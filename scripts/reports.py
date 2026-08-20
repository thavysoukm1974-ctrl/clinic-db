"""
reports.py -- read-only sales reports, computed from the sale history.

    python scripts/reports.py

Nothing here is stored as a running total anywhere: every figure is added up from
the raw sales and sale_items when the report runs. That is the whole point of
recording each small sale -- any question (this month, this week, one medicine)
can be answered later without having designed a separate stored total for it.

Revenue is always summed from sale_items.unit_price, the price FROZEN at the time
of each sale, so reports show what was actually charged -- including free items
(recorded at price 0) and any discounts.
"""

from datetime import date

from init_db import DB_FILE, get_connection

# A date range wide enough to mean "all time", used when no dates are given.
_ALL_TIME = ("0000-01-01", "9999-12-31")


def sales_by_month(conn):
    """Return one row per month that had sales: (month, num_sales, revenue),
    oldest month first. `month` is "YYYY-MM".

      strftime('%Y-%m', s.sale_datetime) -- chop the datetime down to its month.
      COUNT(DISTINCT s.id)               -- how many separate sales that month
                                            (DISTINCT because joining to
                                            sale_items repeats a sale once per line).
      SUM(si.quantity * si.unit_price)   -- the month's revenue.
    """
    return conn.execute(
        """
        SELECT strftime('%Y-%m', s.sale_datetime) AS month,
               COUNT(DISTINCT s.id)               AS num_sales,
               COALESCE(SUM(si.quantity * si.unit_price), 0) AS revenue
        FROM sales s
        JOIN sale_items si ON si.sale_id = s.id
        GROUP BY month
        ORDER BY month
        """
    ).fetchall()


def sales_summary(conn, start_date, end_date):
    """Return (num_sales, revenue) for sales whose date falls between
    start_date and end_date (inclusive). Dates are "YYYY-MM-DD" text.

      date(s.sale_datetime) -- take just the date part of the datetime.
      BETWEEN ? AND ?        -- inclusive range on that date.
    """
    return conn.execute(
        """
        SELECT COUNT(DISTINCT s.id)               AS num_sales,
               COALESCE(SUM(si.quantity * si.unit_price), 0) AS revenue
        FROM sales s
        JOIN sale_items si ON si.sale_id = s.id
        WHERE date(s.sale_datetime) BETWEEN ? AND ?
        """,
        (start_date, end_date),
    ).fetchone()


def best_sellers(conn, start_date=None, end_date=None, limit=5):
    """Return the top-selling medicines by quantity sold in a date range:
    (medicine_name, total_quantity, revenue), most sold first.

    If no dates are given, cover all time. Revenue here is what those units
    actually brought in (frozen prices), so a heavily-given-free medicine can
    sell a lot of units yet show little revenue.
    """
    if start_date is None:
        start_date, end_date = _ALL_TIME
    elif end_date is None:
        end_date = _ALL_TIME[1]

    return conn.execute(
        """
        SELECT m.name,
               SUM(si.quantity)                   AS total_quantity,
               SUM(si.quantity * si.unit_price)   AS revenue
        FROM sale_items si
        JOIN sales s     ON s.id = si.sale_id
        JOIN medicines m ON m.id = si.medicine_id
        WHERE date(s.sale_datetime) BETWEEN ? AND ?
        GROUP BY m.id
        ORDER BY total_quantity DESC
        LIMIT ?
        """,
        (start_date, end_date, limit),
    ).fetchall()


def financial_summary(conn, start_date, end_date):
    """Return (revenue, cost_of_goods_sold, gross_profit) for sales in the range.

      revenue = what we SOLD the units for (frozen sale_items.unit_price).
      cogs    = what those same sold units COST us -- each sold line's batch
                purchase_price, found by joining sale_items.batch_id to batches.
      profit  = revenue - cogs.

    This works because each sold line records WHICH batch it came from, and each
    batch records what we paid for it. (A line with no batch_id contributes 0 to
    cogs -- real sales always set it.)
    """
    revenue, cogs = conn.execute(
        """
        SELECT COALESCE(SUM(si.quantity * si.unit_price), 0)    AS revenue,
               COALESCE(SUM(si.quantity * b.purchase_price), 0) AS cogs
        FROM sales s
        JOIN sale_items si ON si.sale_id = s.id
        LEFT JOIN batches b ON b.id = si.batch_id
        WHERE date(s.sale_datetime) BETWEEN ? AND ?
        """,
        (start_date, end_date),
    ).fetchone()
    return revenue, cogs, revenue - cogs


def reorder_spend(conn, start_date, end_date):
    """Return the total money spent buying stock RECEIVED in the range:
    the sum of received_quantity * purchase_price over those batches.

    Uses received_quantity (the original amount bought), NOT quantity (what's
    left), so selling stock afterwards does not change what we spent buying it.
    """
    return conn.execute(
        """
        SELECT COALESCE(SUM(received_quantity * purchase_price), 0)
        FROM batches
        WHERE received_date BETWEEN ? AND ?
        """,
        (start_date, end_date),
    ).fetchone()[0]


def reorder_spend_by_supplier(conn, start_date, end_date):
    """Return [(supplier_name, spend)] for stock received in the range, biggest
    first -- so you can see how much went to each supplier."""
    return conn.execute(
        """
        SELECT COALESCE(sup.name, '(unknown supplier)')          AS supplier,
               COALESCE(SUM(b.received_quantity * b.purchase_price), 0) AS spend
        FROM batches b
        LEFT JOIN suppliers sup ON sup.id = b.supplier_id
        WHERE b.received_date BETWEEN ? AND ?
        GROUP BY b.supplier_id
        ORDER BY spend DESC
        """,
        (start_date, end_date),
    ).fetchall()


def main():
    conn = get_connection(DB_FILE)
    try:
        print("=== SALES BY MONTH ===")
        rows = sales_by_month(conn)
        if not rows:
            print("  no sales yet")
        for month, num_sales, revenue in rows:
            print(f"  {month}:  {num_sales} sales,  revenue {revenue}")

        # This month so far: from the 1st of the current month up to today.
        today = date.today()
        month_start = today.replace(day=1).isoformat()
        num_sales, revenue = sales_summary(conn, month_start, today.isoformat())
        print(f"\n=== THIS MONTH ({month_start} to {today.isoformat()}) ===")
        print(f"  {num_sales} sales,  revenue {revenue}")

        print("\n=== BEST SELLERS (all time, top 5 by quantity) ===")
        rows = best_sellers(conn)
        if not rows:
            print("  nothing sold yet")
        for name, total_quantity, revenue in rows:
            print(f"  {name:<16} {total_quantity:>5} sold,  revenue {revenue}")

        # Money in vs money out, for this month.
        revenue, cogs, profit = financial_summary(conn, month_start, today.isoformat())
        print(f"\n=== MONEY THIS MONTH ({month_start} to {today.isoformat()}) ===")
        print(f"  revenue (money in from sales):     {revenue}")
        print(f"  cost of goods sold (their cost):   {cogs}")
        print(f"  gross profit (revenue - cost):     {profit}")

        spend = reorder_spend(conn, month_start, today.isoformat())
        print(f"\n  reorder spend (money out to buy stock): {spend}")
        for supplier, amount in reorder_spend_by_supplier(conn, month_start, today.isoformat()):
            print(f"    - {supplier:<18} {amount}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
