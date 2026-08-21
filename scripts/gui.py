"""
gui.py -- the graphical window for the clinic system, using Tkinter.

    python scripts/gui.py

One window, with a TAB per feature (a ttk.Notebook). Each tab is a small frame
whose widgets call functions we already built and tested -- the window holds no
business logic of its own.

Shared picker lists: the medicines / patients / employees / suppliers shown in
dropdowns are kept in one place (self._medicines etc.). When something is added
through a form, we rebuild those lists so every dropdown sees the new item.

Unreal (UMG) parallels: widgets = UMG widgets; .grid()/.pack() = layout;
command=some_function = an "On Clicked" event; root.mainloop() = the event loop.
"""

import tkinter as tk
from tkinter import ttk
from datetime import date

from init_db import DB_FILE, get_connection
from stock import current_stock
from sales import record_sale
from alerts import expiring_soon, low_stock
from visits import patient_history, add_patient, add_employee, record_visit, COMMON_ROLES
from followups import due_follow_ups, add_follow_up
from reports import sales_summary, financial_summary, reorder_spend
from inventory import add_medicine, receive_stock, add_supplier

BOLD = ("Segoe UI", 11, "bold")


def _looks_like_date(text):
    """True if `text` is a valid ISO date like 2027-01-31."""
    try:
        date.fromisoformat(text)
        return True
    except ValueError:
        return False


class ClinicGUI:
    def __init__(self, conn):
        self.conn = conn
        self.root = tk.Tk()
        self.root.title("Clinic system")
        self.root.geometry("720x520")

        # Shared dropdown data, loaded once here and refreshed after any add.
        self._medicines = self._medicine_rows()
        self._patients = self._patient_rows()
        self._employees = self._employee_rows()
        self._suppliers = self._supplier_rows()

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=6, pady=6)
        # daily-use tabs
        notebook.add(self._stock_tab(notebook),     text="Stock")
        notebook.add(self._alerts_tab(notebook),    text="Alerts")
        notebook.add(self._sell_tab(notebook),      text="Record sale")
        notebook.add(self._followups_tab(notebook), text="Follow-ups")
        notebook.add(self._history_tab(notebook),   text="Patient history")
        notebook.add(self._money_tab(notebook),     text="Money")
        # data-entry tabs
        notebook.add(self._add_medicine_tab(notebook),  text="Add medicine")
        notebook.add(self._receive_stock_tab(notebook), text="Receive stock")
        notebook.add(self._add_patient_tab(notebook),   text="Add patient")
        notebook.add(self._add_employee_tab(notebook),  text="Add employee")
        notebook.add(self._add_supplier_tab(notebook),  text="Add supplier")
        notebook.add(self._record_visit_tab(notebook),  text="Record visit")
        notebook.add(self._add_followup_tab(notebook),  text="Add follow-up")

    # --- data used by the dropdowns ------------------------------------------

    def _medicine_rows(self):
        return self.conn.execute(
            "SELECT id, name, unit_price FROM medicines WHERE is_active = 1 ORDER BY name"
        ).fetchall()

    def _patient_rows(self):
        return self.conn.execute("SELECT id, name FROM patients ORDER BY name").fetchall()

    def _employee_rows(self):
        return self.conn.execute("SELECT id, name FROM employees ORDER BY name").fetchall()

    def _supplier_rows(self):
        return self.conn.execute("SELECT id, name FROM suppliers ORDER BY name").fetchall()

    def _reload_medicines(self):
        self._medicines = self._medicine_rows()
        names = [name for _id, name, _p in self._medicines]
        for attr in ("sell_medicine_box", "receive_medicine_box"):
            if hasattr(self, attr):
                getattr(self, attr)["values"] = names
        for attr in ("visit_medicine_box", "followup_medicine_box"):
            if hasattr(self, attr):
                getattr(self, attr)["values"] = ["(none)"] + names

    def _reload_patients(self):
        self._patients = self._patient_rows()
        names = [name for _id, name in self._patients]
        for attr in ("history_patient_box", "visit_patient_box", "followup_patient_box"):
            if hasattr(self, attr):
                getattr(self, attr)["values"] = names

    def _reload_employees(self):
        self._employees = self._employee_rows()
        names = [name for _id, name in self._employees]
        if hasattr(self, "visit_employee_box"):
            self.visit_employee_box["values"] = ["(none)"] + names

    def _reload_suppliers(self):
        self._suppliers = self._supplier_rows()
        if hasattr(self, "supplier_box"):
            self.supplier_box["values"] = ["(none)"] + [n for _id, n in self._suppliers]

    # --- small building helpers ----------------------------------------------

    def _table(self, parent, columns, headings, widths, height=8):
        tree = ttk.Treeview(parent, columns=columns, show="headings", height=height)
        for column, heading, width in zip(columns, headings, widths):
            tree.heading(column, text=heading)
            tree.column(column, width=width, anchor="w")
        return tree

    @staticmethod
    def _fill(tree, rows):
        tree.delete(*tree.get_children())
        for row in rows:
            tree.insert("", "end", values=row)

    def _labeled_entries(self, frame, field_labels, start_row=1):
        """Add a label + text box per (key, label); return {key: Entry} and the
        next free grid row."""
        entries = {}
        row = start_row
        for key, label in field_labels:
            ttk.Label(frame, text=label + ":").grid(row=row, column=0, sticky="e", padx=4, pady=2)
            entry = ttk.Entry(frame, width=26)
            entry.grid(row=row, column=1, sticky="w", padx=4, pady=2)
            entries[key] = entry
            row += 1
        return entries, row

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
        picker = ttk.Frame(frame)
        picker.pack(fill="x", pady=4)
        ttk.Label(picker, text="Medicine:").pack(side="left")
        self.sell_medicine_box = ttk.Combobox(
            picker, state="readonly", width=24,
            values=[name for _id, name, _p in self._medicines])
        self.sell_medicine_box.pack(side="left", padx=4)
        ttk.Label(picker, text="Qty:").pack(side="left")
        self.qty_entry = ttk.Entry(picker, width=6)
        self.qty_entry.pack(side="left", padx=4)
        ttk.Button(picker, text="Add", command=self._add_to_basket).pack(side="left", padx=4)

        self.basket = []
        self.basket_table = self._table(
            frame, ("name", "qty"), ("Medicine", "Qty"), (260, 80), height=7)
        self.basket_table.pack(fill="both", expand=True, pady=6)

        ttk.Button(frame, text="Complete sale", command=self._complete_sale).pack()
        self.sell_result = ttk.Label(frame, text="", foreground="green")
        self.sell_result.pack(pady=4)
        return frame

    def _add_to_basket(self):
        index = self.sell_medicine_box.current()
        if index < 0:
            self.sell_result.config(text="Pick a medicine first.", foreground="red")
            return
        text = self.qty_entry.get().strip()
        if not (text.isdigit() and int(text) > 0):
            self.sell_result.config(text="Quantity must be a whole number > 0.", foreground="red")
            return
        medicine_id, name, _price = self._medicines[index]
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
        picker = ttk.Frame(frame)
        picker.pack(fill="x", pady=4)
        ttk.Label(picker, text="Patient:").pack(side="left")
        self.history_patient_box = ttk.Combobox(
            picker, state="readonly", width=24,
            values=[name for _id, name in self._patients])
        self.history_patient_box.pack(side="left", padx=4)
        ttk.Button(picker, text="Show history", command=self._show_history).pack(side="left", padx=4)

        self.history_table = self._table(
            frame, ("date", "diagnosis", "doctor", "given"),
            ("Date", "Diagnosis", "Seen by", "Medicine given"), (90, 150, 90, 240))
        self.history_table.pack(fill="both", expand=True, pady=6)
        return frame

    def _show_history(self):
        index = self.history_patient_box.current()
        if index < 0:
            return
        patient_id = self._patients[index][0]
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

    # --- Add medicine tab ----------------------------------------------------

    def _add_medicine_tab(self, parent):
        frame = ttk.Frame(parent, padding=10)
        ttk.Label(frame, text="Add a medicine to the catalog", font=BOLD)\
            .grid(row=0, column=0, columnspan=2, pady=6, sticky="w")
        self.med_fields, next_row = self._labeled_entries(frame, [
            ("name", "Name *"), ("form", "Form"), ("unit", "Unit"),
            ("strength", "Strength"), ("category", "Category"),
            ("unit_price", "Price"), ("reorder_threshold", "Reorder at")])
        self.med_partial = tk.IntVar(value=1)
        ttk.Checkbutton(frame, text="Allow partial sale", variable=self.med_partial)\
            .grid(row=next_row, column=1, sticky="w", padx=4, pady=2)
        ttk.Button(frame, text="Add medicine", command=self._submit_medicine)\
            .grid(row=next_row + 1, column=1, sticky="w", padx=4, pady=8)
        self.med_result = ttk.Label(frame, text="", foreground="green")
        self.med_result.grid(row=next_row + 2, column=0, columnspan=2, sticky="w")
        return frame

    def _submit_medicine(self):
        name = self.med_fields["name"].get().strip()
        if not name:
            self.med_result.config(text="Name is required.", foreground="red")
            return
        try:
            price = float(self.med_fields["unit_price"].get().strip() or "0")
        except ValueError:
            self.med_result.config(text="Price must be a number.", foreground="red")
            return
        threshold_text = self.med_fields["reorder_threshold"].get().strip() or "0"
        if not threshold_text.isdigit():
            self.med_result.config(text="Reorder at must be a whole number.", foreground="red")
            return
        add_medicine(
            self.conn, name,
            form=self.med_fields["form"].get().strip() or None,
            unit=self.med_fields["unit"].get().strip() or None,
            strength=self.med_fields["strength"].get().strip() or None,
            category=self.med_fields["category"].get().strip() or None,
            unit_price=price, reorder_threshold=int(threshold_text),
            allow_partial_sale=self.med_partial.get())
        for entry in self.med_fields.values():
            entry.delete(0, "end")
        self._reload_medicines()
        self._refresh_stock()
        self.med_result.config(text=f"Added {name}.", foreground="green")

    # --- Receive stock tab ---------------------------------------------------

    def _receive_stock_tab(self, parent):
        frame = ttk.Frame(parent, padding=10)
        ttk.Label(frame, text="Receive stock (add a batch)", font=BOLD)\
            .grid(row=0, column=0, columnspan=2, pady=6, sticky="w")
        ttk.Label(frame, text="Medicine:").grid(row=1, column=0, sticky="e", padx=4, pady=2)
        self.receive_medicine_box = ttk.Combobox(
            frame, state="readonly", width=24,
            values=[name for _id, name, _p in self._medicines])
        self.receive_medicine_box.grid(row=1, column=1, sticky="w", padx=4, pady=2)
        self.receive_fields, next_row = self._labeled_entries(frame, [
            ("quantity", "Quantity"), ("price", "Buy price / unit"),
            ("expiry", "Expiry (YYYY-MM-DD)")], start_row=2)
        ttk.Label(frame, text="Supplier:").grid(row=next_row, column=0, sticky="e", padx=4, pady=2)
        self.supplier_box = ttk.Combobox(
            frame, state="readonly", width=24,
            values=["(none)"] + [name for _id, name in self._suppliers])
        self.supplier_box.current(0)
        self.supplier_box.grid(row=next_row, column=1, sticky="w", padx=4, pady=2)
        ttk.Button(frame, text="Receive", command=self._submit_receive)\
            .grid(row=next_row + 1, column=1, sticky="w", padx=4, pady=8)
        self.receive_result = ttk.Label(frame, text="", foreground="green")
        self.receive_result.grid(row=next_row + 2, column=0, columnspan=2, sticky="w")
        return frame

    def _submit_receive(self):
        index = self.receive_medicine_box.current()
        if index < 0:
            self.receive_result.config(text="Pick a medicine.", foreground="red")
            return
        quantity_text = self.receive_fields["quantity"].get().strip()
        if not (quantity_text.isdigit() and int(quantity_text) > 0):
            self.receive_result.config(text="Quantity must be a whole number > 0.", foreground="red")
            return
        price_text = self.receive_fields["price"].get().strip()
        price = None
        if price_text:
            try:
                price = float(price_text)
            except ValueError:
                self.receive_result.config(text="Buy price must be a number.", foreground="red")
                return
        expiry = self.receive_fields["expiry"].get().strip() or None
        if expiry and not _looks_like_date(expiry):
            self.receive_result.config(text="Expiry must look like YYYY-MM-DD.", foreground="red")
            return
        supplier_index = self.supplier_box.current()   # 0 = "(none)"
        supplier_id = None if supplier_index <= 0 else self._suppliers[supplier_index - 1][0]
        medicine_id, name, _price = self._medicines[index]
        receive_stock(self.conn, medicine_id, int(quantity_text),
                      purchase_price=price, expiry_date=expiry, supplier_id=supplier_id)
        for entry in self.receive_fields.values():
            entry.delete(0, "end")
        self._refresh_stock()
        self._refresh_alerts()
        self.receive_result.config(text=f"Received {quantity_text} x {name}.", foreground="green")

    # --- Add patient tab -----------------------------------------------------

    def _add_patient_tab(self, parent):
        frame = ttk.Frame(parent, padding=10)
        ttk.Label(frame, text="Add a patient", font=BOLD)\
            .grid(row=0, column=0, columnspan=2, pady=6, sticky="w")
        self.patient_fields, next_row = self._labeled_entries(frame, [
            ("name", "Name *"), ("date_of_birth", "Date of birth (YYYY-MM-DD)"),
            ("sex", "Sex"), ("address", "Address"), ("phone", "Phone")])
        ttk.Button(frame, text="Add patient", command=self._submit_patient)\
            .grid(row=next_row, column=1, sticky="w", padx=4, pady=8)
        self.patient_result = ttk.Label(frame, text="", foreground="green")
        self.patient_result.grid(row=next_row + 1, column=0, columnspan=2, sticky="w")
        return frame

    def _submit_patient(self):
        name = self.patient_fields["name"].get().strip()
        if not name:
            self.patient_result.config(text="Name is required.", foreground="red")
            return
        dob = self.patient_fields["date_of_birth"].get().strip() or None
        if dob and not _looks_like_date(dob):
            self.patient_result.config(text="Date of birth must look like YYYY-MM-DD.", foreground="red")
            return
        add_patient(self.conn, name, date_of_birth=dob,
                    sex=self.patient_fields["sex"].get().strip() or None,
                    address=self.patient_fields["address"].get().strip() or None,
                    phone=self.patient_fields["phone"].get().strip() or None)
        for entry in self.patient_fields.values():
            entry.delete(0, "end")
        self._reload_patients()
        self.patient_result.config(text=f"Added {name}.", foreground="green")

    # --- Add employee tab ----------------------------------------------------

    def _add_employee_tab(self, parent):
        frame = ttk.Frame(parent, padding=10)
        ttk.Label(frame, text="Add a staff member", font=BOLD)\
            .grid(row=0, column=0, columnspan=2, pady=6, sticky="w")
        ttk.Label(frame, text="Name *:").grid(row=1, column=0, sticky="e", padx=4, pady=2)
        self.emp_name = ttk.Entry(frame, width=26)
        self.emp_name.grid(row=1, column=1, sticky="w", padx=4, pady=2)
        ttk.Label(frame, text="Role:").grid(row=2, column=0, sticky="e", padx=4, pady=2)
        # Editable combobox: suggests the usual roles, but any text is allowed.
        self.emp_role = ttk.Combobox(frame, width=24, values=list(COMMON_ROLES))
        self.emp_role.grid(row=2, column=1, sticky="w", padx=4, pady=2)
        self.emp_fields, next_row = self._labeled_entries(frame, [
            ("date_of_birth", "Date of birth (YYYY-MM-DD)"),
            ("address", "Address"), ("phone", "Phone")], start_row=3)
        ttk.Button(frame, text="Add employee", command=self._submit_employee)\
            .grid(row=next_row, column=1, sticky="w", padx=4, pady=8)
        self.emp_result = ttk.Label(frame, text="", foreground="green")
        self.emp_result.grid(row=next_row + 1, column=0, columnspan=2, sticky="w")
        return frame

    def _submit_employee(self):
        name = self.emp_name.get().strip()
        if not name:
            self.emp_result.config(text="Name is required.", foreground="red")
            return
        dob = self.emp_fields["date_of_birth"].get().strip() or None
        if dob and not _looks_like_date(dob):
            self.emp_result.config(text="Date of birth must look like YYYY-MM-DD.", foreground="red")
            return
        add_employee(self.conn, name,
                     role=self.emp_role.get().strip() or None,
                     date_of_birth=dob,
                     address=self.emp_fields["address"].get().strip() or None,
                     phone=self.emp_fields["phone"].get().strip() or None)
        self.emp_name.delete(0, "end")
        self.emp_role.set("")
        for entry in self.emp_fields.values():
            entry.delete(0, "end")
        self._reload_employees()
        self.emp_result.config(text=f"Added {name}.", foreground="green")

    # --- Add supplier tab ----------------------------------------------------

    def _add_supplier_tab(self, parent):
        frame = ttk.Frame(parent, padding=10)
        ttk.Label(frame, text="Add a supplier", font=BOLD)\
            .grid(row=0, column=0, columnspan=2, pady=6, sticky="w")
        self.supplier_fields, next_row = self._labeled_entries(frame, [
            ("name", "Name *"), ("phone", "Phone"), ("note", "Note")])
        ttk.Button(frame, text="Add supplier", command=self._submit_supplier)\
            .grid(row=next_row, column=1, sticky="w", padx=4, pady=8)
        self.supplier_result = ttk.Label(frame, text="", foreground="green")
        self.supplier_result.grid(row=next_row + 1, column=0, columnspan=2, sticky="w")
        return frame

    def _submit_supplier(self):
        name = self.supplier_fields["name"].get().strip()
        if not name:
            self.supplier_result.config(text="Name is required.", foreground="red")
            return
        add_supplier(self.conn, name,
                     phone=self.supplier_fields["phone"].get().strip() or None,
                     note=self.supplier_fields["note"].get().strip() or None)
        for entry in self.supplier_fields.values():
            entry.delete(0, "end")
        self._reload_suppliers()
        self.supplier_result.config(text=f"Added {name}.", foreground="green")

    # --- Record visit tab ----------------------------------------------------

    def _record_visit_tab(self, parent):
        frame = ttk.Frame(parent, padding=10)
        ttk.Label(frame, text="Record a patient visit", font=BOLD)\
            .grid(row=0, column=0, columnspan=2, pady=6, sticky="w")

        ttk.Label(frame, text="Patient *:").grid(row=1, column=0, sticky="e", padx=4, pady=2)
        self.visit_patient_box = ttk.Combobox(
            frame, state="readonly", width=24,
            values=[name for _id, name in self._patients])
        self.visit_patient_box.grid(row=1, column=1, sticky="w", padx=4, pady=2)

        ttk.Label(frame, text="Doctor:").grid(row=2, column=0, sticky="e", padx=4, pady=2)
        self.visit_employee_box = ttk.Combobox(
            frame, state="readonly", width=24,
            values=["(none)"] + [name for _id, name in self._employees])
        self.visit_employee_box.current(0)
        self.visit_employee_box.grid(row=2, column=1, sticky="w", padx=4, pady=2)

        self.visit_fields, next_row = self._labeled_entries(frame, [
            ("visit_date", "Date (YYYY-MM-DD)"), ("diagnosis", "Diagnosis"),
            ("treatment", "Treatment")], start_row=3)
        self.visit_fields["visit_date"].insert(0, date.today().isoformat())

        ttk.Label(frame, text="Give medicine:").grid(row=next_row, column=0, sticky="e", padx=4, pady=2)
        self.visit_medicine_box = ttk.Combobox(
            frame, state="readonly", width=24,
            values=["(none)"] + [name for _id, name, _p in self._medicines])
        self.visit_medicine_box.current(0)
        self.visit_medicine_box.grid(row=next_row, column=1, sticky="w", padx=4, pady=2)
        ttk.Label(frame, text="Qty given:").grid(row=next_row + 1, column=0, sticky="e", padx=4, pady=2)
        self.visit_qty = ttk.Entry(frame, width=10)
        self.visit_qty.grid(row=next_row + 1, column=1, sticky="w", padx=4, pady=2)

        ttk.Button(frame, text="Save visit", command=self._submit_visit)\
            .grid(row=next_row + 2, column=1, sticky="w", padx=4, pady=8)
        self.visit_result = ttk.Label(frame, text="", foreground="green")
        self.visit_result.grid(row=next_row + 3, column=0, columnspan=2, sticky="w")
        return frame

    def _submit_visit(self):
        patient_index = self.visit_patient_box.current()
        if patient_index < 0:
            self.visit_result.config(text="Pick a patient.", foreground="red")
            return
        patient_id = self._patients[patient_index][0]

        employee_index = self.visit_employee_box.current()
        employee_id = None if employee_index <= 0 else self._employees[employee_index - 1][0]

        visit_date = self.visit_fields["visit_date"].get().strip() or None
        if visit_date and not _looks_like_date(visit_date):
            self.visit_result.config(text="Date must look like YYYY-MM-DD.", foreground="red")
            return

        # Optional medicine given during the visit.
        medicines = None
        medicine_index = self.visit_medicine_box.current()
        if medicine_index > 0:   # 0 = "(none)"
            qty_text = self.visit_qty.get().strip()
            if not (qty_text.isdigit() and int(qty_text) > 0):
                self.visit_result.config(text="Qty given must be a whole number > 0.", foreground="red")
                return
            medicine_id = self._medicines[medicine_index - 1][0]
            medicines = [(medicine_id, int(qty_text))]

        visit_id, sale_id, shortfalls = record_visit(
            self.conn, patient_id, employee_id=employee_id, visit_date=visit_date,
            diagnosis=self.visit_fields["diagnosis"].get().strip() or None,
            treatment=self.visit_fields["treatment"].get().strip() or None,
            medicines=medicines)

        message = f"Recorded visit #{visit_id}."
        if sale_id is not None:
            message += f" (medicine sold, sale #{sale_id})"
        if shortfalls:
            message += " some medicine was short of stock"
        # Clear the medicine part; keep patient/date for convenience.
        self.visit_qty.delete(0, "end")
        self.visit_medicine_box.current(0)
        self._refresh_stock()
        self._refresh_money()
        self.visit_result.config(text=message, foreground="green")

    # --- Add follow-up tab ---------------------------------------------------

    def _add_followup_tab(self, parent):
        frame = ttk.Frame(parent, padding=10)
        ttk.Label(frame, text="Add a follow-up (check-in when medicine runs out)", font=BOLD)\
            .grid(row=0, column=0, columnspan=2, pady=6, sticky="w")

        ttk.Label(frame, text="Patient *:").grid(row=1, column=0, sticky="e", padx=4, pady=2)
        self.followup_patient_box = ttk.Combobox(
            frame, state="readonly", width=24,
            values=[name for _id, name in self._patients])
        self.followup_patient_box.grid(row=1, column=1, sticky="w", padx=4, pady=2)

        ttk.Label(frame, text="Medicine:").grid(row=2, column=0, sticky="e", padx=4, pady=2)
        self.followup_medicine_box = ttk.Combobox(
            frame, state="readonly", width=24,
            values=["(none)"] + [name for _id, name, _p in self._medicines])
        self.followup_medicine_box.current(0)
        self.followup_medicine_box.grid(row=2, column=1, sticky="w", padx=4, pady=2)

        self.followup_fields, next_row = self._labeled_entries(frame, [
            ("quantity_given", "Quantity given"), ("daily_dose", "Daily dose"),
            ("start_date", "Start date (YYYY-MM-DD)")], start_row=3)
        self.followup_fields["start_date"].insert(0, date.today().isoformat())

        ttk.Button(frame, text="Add follow-up", command=self._submit_followup)\
            .grid(row=next_row, column=1, sticky="w", padx=4, pady=8)
        self.followup_result = ttk.Label(frame, text="", foreground="green")
        self.followup_result.grid(row=next_row + 1, column=0, columnspan=2, sticky="w")
        return frame

    def _submit_followup(self):
        patient_index = self.followup_patient_box.current()
        if patient_index < 0:
            self.followup_result.config(text="Pick a patient.", foreground="red")
            return
        patient_id = self._patients[patient_index][0]

        medicine_index = self.followup_medicine_box.current()
        medicine_id = None if medicine_index <= 0 else self._medicines[medicine_index - 1][0]

        qty_text = self.followup_fields["quantity_given"].get().strip()
        if not (qty_text.isdigit() and int(qty_text) > 0):
            self.followup_result.config(text="Quantity given must be a whole number > 0.", foreground="red")
            return
        dose_text = self.followup_fields["daily_dose"].get().strip()
        try:
            daily_dose = float(dose_text)
            if daily_dose <= 0:
                raise ValueError
        except ValueError:
            self.followup_result.config(text="Daily dose must be a number > 0.", foreground="red")
            return
        start_date = self.followup_fields["start_date"].get().strip() or None
        if start_date and not _looks_like_date(start_date):
            self.followup_result.config(text="Start date must look like YYYY-MM-DD.", foreground="red")
            return

        _fid, run_out = add_follow_up(
            self.conn, patient_id, medicine_id, int(qty_text), daily_dose,
            start_date=start_date)
        self.followup_fields["quantity_given"].delete(0, "end")
        self.followup_fields["daily_dose"].delete(0, "end")
        self._refresh_followups()
        self.followup_result.config(
            text=f"Follow-up saved. Expected to run out on {run_out}.", foreground="green")

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
