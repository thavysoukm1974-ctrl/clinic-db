"""
gui.py -- the graphical window for the clinic system, using Tkinter.

    python scripts/gui.py

One window, with a TAB per feature (a ttk.Notebook). Each tab is a small frame
whose widgets call functions we already built and tested -- the window holds no
business logic of its own, exactly like the text menu did.

Unreal (UMG) parallels, if that helps:
  * widgets (tables, buttons, text boxes) = UMG widgets,
  * .pack()/frames = laying widgets out (instead of dragging on a canvas),
  * command=some_function on a button = an "On Clicked" event,
  * root.mainloop() = the loop that keeps the window alive, like the game loop.
"""

import tkinter as tk
from tkinter import ttk
from datetime import date

from init_db import DB_FILE, get_connection
from stock import current_stock
from sales import record_sale
from alerts import expiring_soon, low_stock
from visits import patient_history
from followups import due_follow_ups
from reports import sales_summary, financial_summary, reorder_spend

BOLD = ("Segoe UI", 11, "bold")


class ClinicGUI:
    def __init__(self, conn):
        self.conn = conn
        self.root = tk.Tk()
        self.root.title("Clinic system")
        self.root.geometry("700x500")

        # The Notebook holds the tabs. Each tab is a Frame we build below.
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=6, pady=6)
        notebook.add(self._stock_tab(notebook),     text="Stock")
        notebook.add(self._alerts_tab(notebook),    text="Alerts")
        notebook.add(self._sell_tab(notebook),      text="Record sale")
        notebook.add(self._followups_tab(notebook), text="Follow-ups")
        notebook.add(self._history_tab(notebook),   text="Patient history")
        notebook.add(self._money_tab(notebook),     text="Money")

    # --- a small helper so every table is built the same way -----------------

    def _table(self, parent, columns, headings, widths, height=8):
        tree = ttk.Treeview(parent, columns=columns, show="headings", height=height)
        for column, heading, width in zip(columns, headings, widths):
            tree.heading(column, text=heading)
            tree.column(column, width=width, anchor="w")
        return tree

    @staticmethod
    def _fill(tree, rows):
        """Replace everything in a table with `rows` (each a tuple of values)."""
        tree.delete(*tree.get_children())
        for row in rows:
            tree.insert("", "end", values=row)

    # --- Stock tab -----------------------------------------------------------

    def _stock_tab(self, parent):
        frame = ttk.Frame(parent, padding=10)
        ttk.Label(frame, text="Current stock on hand", font=BOLD).pack(pady=6)
        self.stock_table = self._table(
            frame, ("name", "on_hand", "unit"),
            ("Medicine", "On hand", "Unit"), (260, 90, 120))
        self.stock_table.pack(fill="both", expand=True)
        ttk.Button(frame, text="Refresh", command=self._refresh_stock).pack(pady=6)
        self._refresh_stock()
        return frame

    def _refresh_stock(self):
        self._fill(self.stock_table,
                   [(name, on_hand, unit or "units")
                    for _id, name, unit, on_hand in current_stock(self.conn)])

    # --- Alerts tab ----------------------------------------------------------

    def _alerts_tab(self, parent):
        frame = ttk.Frame(parent, padding=10)
        ttk.Label(frame, text="Expiring soon (within 30 days)", font=BOLD).pack(anchor="w")
        self.expiry_table = self._table(
            frame, ("name", "qty", "expiry", "when"),
            ("Medicine", "Qty", "Expiry", "Status"), (170, 60, 110, 150), height=6)
        self.expiry_table.pack(fill="both", expand=True)

        ttk.Label(frame, text="Low on stock", font=BOLD).pack(anchor="w", pady=(10, 0))
        self.low_table = self._table(
            frame, ("name", "on_hand", "threshold"),
            ("Medicine", "On hand", "Reorder at"), (220, 90, 110), height=5)
        self.low_table.pack(fill="both", expand=True)

        ttk.Button(frame, text="Refresh", command=self._refresh_alerts).pack(pady=6)
        self._refresh_alerts()
        return frame

    def _refresh_alerts(self):
        expiry_rows = []
        for name, _batch_id, qty, expiry, days_left in expiring_soon(self.conn, days=30):
            when = f"EXPIRED {-days_left}d ago" if days_left < 0 else f"in {days_left}d"
            expiry_rows.append((name, qty, expiry, when))
        self._fill(self.expiry_table, expiry_rows)
        self._fill(self.low_table, low_stock(self.conn))

    # --- Record sale tab -----------------------------------------------------

    def _sell_tab(self, parent):
        frame = ttk.Frame(parent, padding=10)

        # The medicines we can pick from (id, name, price).
        self.sell_medicines = self.conn.execute(
            "SELECT id, name, unit_price FROM medicines WHERE is_active = 1 ORDER BY name"
        ).fetchall()

        picker = ttk.Frame(frame)
        picker.pack(fill="x", pady=4)
        ttk.Label(picker, text="Medicine:").pack(side="left")
        self.medicine_box = ttk.Combobox(
            picker, state="readonly", width=24,
            values=[name for _id, name, _price in self.sell_medicines])
        self.medicine_box.pack(side="left", padx=4)
        ttk.Label(picker, text="Qty:").pack(side="left")
        self.qty_entry = ttk.Entry(picker, width=6)
        self.qty_entry.pack(side="left", padx=4)
        ttk.Button(picker, text="Add", command=self._add_to_basket).pack(side="left", padx=4)

        self.basket = []   # list of (medicine_id, quantity)
        self.basket_table = self._table(
            frame, ("name", "qty"), ("Medicine", "Qty"), (260, 80), height=7)
        self.basket_table.pack(fill="both", expand=True, pady=6)

        ttk.Button(frame, text="Complete sale", command=self._complete_sale).pack()
        self.sell_result = ttk.Label(frame, text="", foreground="green")
        self.sell_result.pack(pady=4)
        return frame

    def _add_to_basket(self):
        index = self.medicine_box.current()   # -1 if nothing chosen
        if index < 0:
            self.sell_result.config(text="Pick a medicine first.", foreground="red")
            return
        text = self.qty_entry.get().strip()
        if not (text.isdigit() and int(text) > 0):
            self.sell_result.config(text="Quantity must be a whole number > 0.", foreground="red")
            return
        medicine_id, name, _price = self.sell_medicines[index]
        quantity = int(text)
        self.basket.append((medicine_id, quantity))
        self.basket_table.insert("", "end", values=(name, quantity))
        self.qty_entry.delete(0, "end")
        self.sell_result.config(text=f"Added {quantity} x {name}.", foreground="green")

    def _complete_sale(self):
        if not self.basket:
            self.sell_result.config(text="Basket is empty.", foreground="red")
            return
        sale_id, shortfalls = record_sale(self.conn, self.basket)
        if sale_id is None:
            message = "Nothing could be sold (out of stock)."
        else:
            total = self.conn.execute(
                "SELECT SUM(quantity * unit_price) FROM sale_items WHERE sale_id = ?",
                (sale_id,)).fetchone()[0]
            message = f"Recorded sale #{sale_id}, total {total}."
        if shortfalls:
            message += f" ({len(shortfalls)} item(s) short)"
        # Reset the basket and refresh the views that a sale changes.
        self.basket = []
        self.basket_table.delete(*self.basket_table.get_children())
        self._refresh_stock()
        self._refresh_money()
        self.sell_result.config(text=message, foreground="green")

    # --- Follow-ups tab ------------------------------------------------------

    def _followups_tab(self, parent):
        frame = ttk.Frame(parent, padding=10)
        ttk.Label(frame, text="Patients due for a check-in", font=BOLD).pack(pady=6)
        self.followups_table = self._table(
            frame, ("patient", "phone", "medicine", "runout", "overdue"),
            ("Patient", "Phone", "Medicine", "Ran out", "Days ago"),
            (150, 120, 130, 100, 80))
        self.followups_table.pack(fill="both", expand=True)
        ttk.Button(frame, text="Refresh", command=self._refresh_followups).pack(pady=6)
        self._refresh_followups()
        return frame

    def _refresh_followups(self):
        self._fill(self.followups_table,
                   [(patient, phone, medicine, run_out, days_overdue)
                    for _fid, patient, phone, medicine, run_out, days_overdue
                    in due_follow_ups(self.conn)])

    # --- Patient history tab -------------------------------------------------

    def _history_tab(self, parent):
        frame = ttk.Frame(parent, padding=10)
        self.patients = self.conn.execute(
            "SELECT id, name FROM patients ORDER BY name").fetchall()

        picker = ttk.Frame(frame)
        picker.pack(fill="x", pady=4)
        ttk.Label(picker, text="Patient:").pack(side="left")
        self.patient_box = ttk.Combobox(
            picker, state="readonly", width=24,
            values=[name for _id, name in self.patients])
        self.patient_box.pack(side="left", padx=4)
        ttk.Button(picker, text="Show history", command=self._show_history).pack(side="left", padx=4)

        self.history_table = self._table(
            frame, ("date", "diagnosis", "doctor", "given"),
            ("Date", "Diagnosis", "Seen by", "Medicine given"), (90, 150, 90, 240))
        self.history_table.pack(fill="both", expand=True, pady=6)
        return frame

    def _show_history(self):
        index = self.patient_box.current()
        if index < 0:
            return
        patient_id = self.patients[index][0]
        rows = []
        for _vid, vdate, diagnosis, _treatment, doctor, medicines in \
                patient_history(self.conn, patient_id):
            given = ", ".join(f"{qty}x {name}" for name, qty, _price in medicines) or "-"
            rows.append((vdate, diagnosis, doctor or "?", given))
        self._fill(self.history_table, rows)

    # --- Money tab -----------------------------------------------------------

    def _money_tab(self, parent):
        frame = ttk.Frame(parent, padding=10)
        ttk.Label(frame, text="Money this month", font=BOLD).pack(pady=6)
        self.money_label = ttk.Label(frame, text="", justify="left", font=("Consolas", 10))
        self.money_label.pack(anchor="w")
        ttk.Button(frame, text="Refresh", command=self._refresh_money).pack(pady=6)
        self._refresh_money()
        return frame

    def _refresh_money(self):
        today = date.today()
        start, end = today.replace(day=1).isoformat(), today.isoformat()
        num_sales, revenue = sales_summary(self.conn, start, end)
        _revenue, cogs, profit = financial_summary(self.conn, start, end)
        spend = reorder_spend(self.conn, start, end)
        self.money_label.config(text=(
            f"{start}  to  {end}\n\n"
            f"Sales:          {num_sales}\n"
            f"Revenue:        {revenue}\n"
            f"Cost of sold:   {cogs}\n"
            f"Gross profit:   {profit}\n"
            f"Reorder spend:  {spend}"))

    # --- run -----------------------------------------------------------------

    def run(self):
        self.root.mainloop()


def main():
    conn = get_connection(DB_FILE)
    try:
        ClinicGUI(conn).run()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
