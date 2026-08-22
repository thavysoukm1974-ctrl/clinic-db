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


def revenue_by_channel(conn, start_date, end_date):
    """Split sales revenue by how the sale happened, for the date range.
    Returns {"visit": (num_sales, revenue), "walkin": (num_sales, revenue)}.

    A sale with a visit_id came from a patient visit; a sale with none was a
    walk-in counter sale. That is the whole difference between the two channels.
    """
    result = {"visit": (0, 0.0), "walkin": (0, 0.0)}
    for channel, num_sales, revenue in conn.execute(
        """
        SELECT CASE WHEN s.visit_id IS NULL THEN 'walkin' ELSE 'visit' END AS channel,
               COUNT(DISTINCT s.id),
               COALESCE(SUM(si.quantity * si.unit_price), 0)
        FROM sales s
        JOIN sale_items si ON si.sale_id = s.id
        WHERE date(s.sale_datetime) BETWEEN ? AND ?
        GROUP BY channel
        """,
        (start_date, end_date),
    ):
        result[channel] = (num_sales, revenue)
    return result


def reorder_spend_by_medicine(conn, start_date, end_date):
    """Return [(medicine_name, spend)] for stock received in the range, biggest
    first -- how much restocking money went to each medicine."""
    return conn.execute(
        """
        SELECT m.name,
               COALESCE(SUM(b.received_quantity * b.purchase_price), 0) AS spend
        FROM batches b
        JOIN medicines m ON m.id = b.medicine_id
        WHERE b.received_date BETWEEN ? AND ?
        GROUP BY b.medicine_id
        ORDER BY spend DESC
        """,
        (start_date, end_date),
    ).fetchall()


def sales_by_employee(conn, start_date, end_date):
    """Return [(seller_name, num_sales, revenue)] for the range, biggest first.
    Sales with no recorded seller are grouped under '(unrecorded)'."""
    return conn.execute(
        """
        SELECT COALESCE(e.name, '(unrecorded)') AS seller,
               COUNT(DISTINCT s.id),
               COALESCE(SUM(si.quantity * si.unit_price), 0) AS revenue
        FROM sales s
        JOIN sale_items si     ON si.sale_id = s.id
        LEFT JOIN employees e  ON e.id = s.employee_id
        WHERE date(s.sale_datetime) BETWEEN ? AND ?
        GROUP BY s.employee_id
        ORDER BY revenue DESC
        """,
        (start_date, end_date),
    ).fetchall()


def revenue_split_by_paid(conn, start_date, end_date):
    """Split sales revenue in the range into (received, owed):
      received = total of sales already PAID (money in hand),
      owed     = total of sales still UNPAID (debts to collect).
    received + owed = the full revenue if every debt is paid.
    """
    result = {"paid": 0.0, "owed": 0.0}
    for status, amount in conn.execute(
        """
        SELECT CASE WHEN s.paid = 1 THEN 'paid' ELSE 'owed' END,
               COALESCE(SUM(si.quantity * si.unit_price), 0)
        FROM sales s
        JOIN sale_items si ON si.sale_id = s.id
        WHERE date(s.sale_datetime) BETWEEN ? AND ?
        GROUP BY 1
        """,
        (start_date, end_date),
    ):
        result[status] = amount
    return result["paid"], result["owed"]


def debts_in_period(conn, start_date, end_date):
    """Return [(who, amount)] for unpaid sales made in the range, biggest first."""
    return conn.execute(
        """
        SELECT COALESCE(pv.name, pd.name, '?') AS who,
               COALESCE(SUM(si.quantity * si.unit_price), 0) AS amount
        FROM sales s
        JOIN sale_items si     ON si.sale_id = s.id
        LEFT JOIN visits v     ON v.id = s.visit_id
        LEFT JOIN patients pv  ON pv.id = v.patient_id
        LEFT JOIN patients pd  ON pd.id = s.patient_id
        WHERE s.paid = 0 AND date(s.sale_datetime) BETWEEN ? AND ?
        GROUP BY s.id
        ORDER BY amount DESC
        """,
        (start_date, end_date),
    ).fetchall()


def period_report_text(conn, start, end, title_lines):
    """Build a full, human-readable report for any date range [start, end] as one
    text string. `title_lines` are the heading lines (report name and period).
    Everything is computed from the raw records, so it is always up to date. Used
    by monthly_report_text and daily_report_text below.
    """
    num_sales, revenue = sales_summary(conn, start, end)
    _revenue, cogs, profit = financial_summary(conn, start, end)
    channel = revenue_by_channel(conn, start, end)
    spend = reorder_spend(conn, start, end)
    received, owed = revenue_split_by_paid(conn, start, end)
    visit_count, visit_rev = channel["visit"]
    walkin_count, walkin_rev = channel["walkin"]

    lines = list(title_lines)
    lines.append("")
    lines.append("MONEY IN  (sales)")
    lines.append(f"  Total sales:          {num_sales}")
    lines.append(f"  Revenue received:     {received:>12.2f}")
    lines.append(f"  Still owed (unpaid):  {owed:>12.2f}")
    lines.append(f"  Total if all paid:    {received + owed:>12.2f}")
    lines.append("")
    lines.append("  By channel:")
    lines.append(f"    from patient visits:{visit_rev:>12.2f}   ({visit_count} sales)")
    lines.append(f"    from walk-in buyers:{walkin_rev:>12.2f}   ({walkin_count} sales)")
    lines.append("")
    lines.append("  Best sellers (by quantity):")
    best = best_sellers(conn, start, end)
    if not best:
        lines.append("    (no sales)")
    for name, quantity, item_revenue in best:
        lines.append(f"    {name:<22}{quantity:>5} sold {item_revenue:>11.2f}")
    lines.append("")
    lines.append("SALES BY STAFF  (who sold)")
    staff = sales_by_employee(conn, start, end)
    if not staff:
        lines.append("    (no sales)")
    for seller, count, seller_revenue in staff:
        lines.append(f"    {seller:<22}{count:>4} sales {seller_revenue:>11.2f}")
    lines.append("")
    lines.append("DEBTS  (unpaid sales this period)")
    debts = debts_in_period(conn, start, end)
    if not debts:
        lines.append("    (none)")
    for who, amount in debts:
        lines.append(f"    {who:<22}{amount:>14.2f}")
    lines.append(f"  Total owed:           {owed:>12.2f}")
    lines.append("")
    lines.append("MONEY OUT  (restocking)")
    lines.append(f"  Total reorder spend:  {spend:>12.2f}")
    lines.append("  By supplier:")
    for supplier, amount in reorder_spend_by_supplier(conn, start, end):
        lines.append(f"    {supplier:<22}{amount:>14.2f}")
    lines.append("  By medicine:")
    for name, amount in reorder_spend_by_medicine(conn, start, end):
        lines.append(f"    {name:<22}{amount:>14.2f}")
    lines.append("")
    lines.append("PROFIT  (on what was sold)")
    lines.append(f"  Revenue (all sales):  {revenue:>12.2f}")
    lines.append(f"  Cost of goods sold:   {cogs:>12.2f}")
    lines.append(f"  Gross profit:         {profit:>12.2f}")
    lines.append("")
    return "\n".join(lines)


def monthly_report_text(conn, month):
    """The report for one month. `month` is "YYYY-MM"."""
    return period_report_text(
        conn, f"{month}-01", f"{month}-31",   # ISO text compare covers the month
        ["CLINIC MONTHLY REPORT", f"Month: {month}"])


def daily_report_text(conn, day):
    """The report for one day. `day` is "YYYY-MM-DD"."""
    return period_report_text(
        conn, day, day,
        ["CLINIC DAILY REPORT", f"Day: {day}"])


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
