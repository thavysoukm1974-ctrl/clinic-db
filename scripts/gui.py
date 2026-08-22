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

import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import date
from pathlib import Path

import updater
from init_db import DB_FILE, get_connection, ensure_database
from stock import current_stock
from sales import record_sale, outstanding_debts, mark_sale_paid
from alerts import expiring_soon, low_stock
from visits import patient_history, add_patient, add_employee, record_visit, COMMON_ROLES
from followups import open_follow_ups, add_follow_up
from reports import monthly_report_text, daily_report_text
from inventory import add_medicine, receive_stock, add_supplier, COMMON_FORMS, COMMON_UNITS

# --- one place for the whole look (fonts + colours) ----------------------------
# Change these and the entire window changes, because _apply_style() below feeds
# them into ttk.Style -- a central "stylesheet" that every widget of a type uses.
FONT = ("Segoe UI", 10)
BOLD = ("Segoe UI", 11, "bold")
BG = "#f4f6f8"        # window background (soft grey)
ACCENT = "#2c6e8f"    # headings / selected tab / table header (teal-blue)
STRIPE = "#eaf0f4"    # shading for every other table row
TEXT = "#1f2a30"      # normal text


def _looks_like_date(text):
    """True if `text` is a valid ISO date like 2027-01-31."""
    try:
        date.fromisoformat(text)
        return True
    except ValueError:
        return False


def _looks_like_month(text):
    """True if `text` is a valid year-month like 2026-08."""
    return _looks_like_date(text + "-01")


class ClinicGUI:
    def __init__(self, conn):
        self.conn = conn
        self.root = tk.Tk()
        self.root.title("Clinic system")
        self.root.geometry("1000x560")
        self.root.minsize(900, 520)
        self._apply_style()

        # Shared dropdown data, loaded once here and refreshed after any add.
        self._medicines = self._medicine_rows()
        self._patients = self._patient_rows()
        self._employees = self._employee_rows()
        self._suppliers = self._supplier_rows()

        # A thin status bar along the bottom: the version, and a manual update
        # check. Packed first with side=bottom so it reserves the bottom strip.
        status = ttk.Frame(self.root, padding=(8, 2))
        status.pack(side="bottom", fill="x")
        ttk.Label(status, text=f"Clinic system  v{updater.CURRENT_VERSION}",
                  foreground="#888").pack(side="left")
        ttk.Button(status, text="Check for updates",
                   command=self._check_updates_now).pack(side="right")
        self.status_label = ttk.Label(status, text="", foreground="#888")
        self.status_label.pack(side="right", padx=8)

        # Layout: VIEW buttons on the far left, ADD/RECORD buttons on the far
        # right, and ONE shared content area in the middle. Clicking any button
        # shows just that one panel in the middle -- one open at a time.
        container = ttk.Frame(self.root, padding=8)
        container.pack(fill="both", expand=True)
        container.columnconfigure(2, weight=1)   # the middle content stretches
        container.rowconfigure(0, weight=1)

        self._content = ttk.Frame(container)     # the single panel area
        self._content.grid(row=0, column=2, sticky="nsew")

        view_items = [
            ("Stock",           self._stock_tab),
            ("Alerts",          self._alerts_tab),
            ("Follow-ups",      self._followups_tab),
            ("Patient history", self._history_tab),
            ("Money",           self._money_tab),
            ("Debts",           self._debts_tab),
        ]
        add_items = [
            ("Record sale",   self._sell_tab),
            ("Record visit",  self._record_visit_tab),
            ("Add medicine",  self._add_medicine_tab),
            ("Receive stock", self._receive_stock_tab),
            ("Add patient",   self._add_patient_tab),
            ("Add employee",  self._add_employee_tab),
            ("Add supplier",  self._add_supplier_tab),
            ("Add follow-up", self._add_followup_tab),
        ]
        # Build every panel once, all parented to the single content area.
        self._panels = {label: build(self._content)
                        for label, build in view_items + add_items}

        # Group the buttons by what the user is doing, so related panels sit
        # together (same left/right layout -- just organised into groups).
        view_groups = [
            ("Stock",    ["Stock", "Alerts"]),
            ("Patients", ["Patient history", "Follow-ups"]),
            ("Reports",  ["Money", "Debts"]),
        ]
        add_groups = [
            ("Selling",           ["Record sale"]),
            ("Patients & visits", ["Record visit", "Add patient", "Add follow-up"]),
            ("Stock & catalog",   ["Add medicine", "Receive stock", "Add supplier"]),
            ("Staff",             ["Add employee"]),
        ]
        self._nav_column(container, "View", view_groups)\
            .grid(row=0, column=0, sticky="ns")
        ttk.Separator(container, orient="vertical")\
            .grid(row=0, column=1, sticky="ns", padx=8)
        ttk.Separator(container, orient="vertical")\
            .grid(row=0, column=3, sticky="ns", padx=8)
        self._nav_column(container, "Add / record", add_groups)\
            .grid(row=0, column=4, sticky="ns")

        self._show("Stock")   # show one panel to begin with

        # In the installed app, quietly check for a newer version shortly after
        # the window opens (in the background, so a slow network never blocks it).
        if getattr(sys, "frozen", False):
            self.root.after(1500, self._auto_check_updates)

    # --- "?" help buttons -----------------------------------------------------

    def _help_button(self, parent, title, text):
        """A small "?" button that pops up an explanation window when clicked.
        Used instead of printing notes on the screen -- the explanation is there
        when wanted and out of the way when not."""
        def show_help():
            popup = tk.Toplevel(self.root)
            popup.title(title)
            popup.configure(bg=BG)
            popup.resizable(False, False)
            ttk.Label(popup, text=text, padding=14, justify="left",
                      wraplength=380).pack()
            ttk.Button(popup, text="OK", command=popup.destroy).pack(pady=(0, 10))
            popup.transient(self.root)   # stay on top of the main window
            popup.grab_set()             # take focus until closed
        return ttk.Button(parent, text="?", width=2, command=show_help)

    # --- navigation: a button column, and showing one panel at a time --------

    def _nav_column(self, parent, title, groups):
        """A titled column of buttons, arranged in GROUPS so related panels sit
        together. `groups` is a list of (group_heading, [button_labels]). Each
        button shows its panel in the shared content area. Returns the column."""
        column = ttk.Frame(parent)
        ttk.Label(column, text=title, font=BOLD).pack(anchor="w", pady=(0, 4))
        for heading, labels in groups:
            # A small, muted sub-heading separates one group of buttons from the next.
            ttk.Label(column, text=heading, font=("Segoe UI", 9), foreground="#888")\
                .pack(anchor="w", pady=(8, 2))
            for label in labels:
                ttk.Button(column, text=label, width=16,
                           command=lambda n=label: self._show(n)).pack(fill="x", pady=1)
        return column

    def _show(self, name):
        """Hide every panel, then show the chosen one in the content area."""
        for panel in self._panels.values():
            panel.pack_forget()
        self._panels[name].pack(fill="both", expand=True)

    # --- software updates -----------------------------------------------------

    def _auto_check_updates(self):
        """Check for an update in a background thread (so the window never
        freezes), and if one is found, offer it on the main thread."""
        def worker():
            info = updater.check_for_update()
            if info:
                # after(0, ...) hops back to the UI thread, which is the only
                # thread allowed to touch Tk widgets.
                self.root.after(0, lambda: self._offer_update(info))
        threading.Thread(target=worker, daemon=True).start()

    def _check_updates_now(self):
        """The manual 'Check for updates' button."""
        self.status_label.config(text="Checking...")
        self.root.update_idletasks()
        info = updater.check_for_update()
        self.status_label.config(text="")
        if info is None:
            messagebox.showinfo(
                "Up to date",
                f"You have the latest version (v{updater.CURRENT_VERSION}).")
        else:
            self._offer_update(info)

    def _offer_update(self, info):
        """Ask whether to install the found update; if yes, download, verify,
        swap it in, and restart."""
        notes = info["notes"] or "(no description)"
        if not messagebox.askyesno(
                "Update available",
                f"Version {info['version']} is available "
                f"(you have {updater.CURRENT_VERSION}).\n\n{notes}\n\n"
                "Install it now? The app will close and reopen."):
            return
        if not getattr(sys, "frozen", False):
            messagebox.showinfo(
                "Update", "Updates install in the packaged app (the .exe), "
                "not when running from source.")
            return
        try:
            self.status_label.config(text="Downloading update...")
            self.root.update_idletasks()
            new_exe = updater.download_update(info, Path(sys.executable).parent)
            updater.apply_update(new_exe)
        except Exception as error:
            self.status_label.config(text="")
            messagebox.showerror("Update failed", f"Could not install the update:\n{error}")
            return
        # The new version is in place; it is used on the next launch. We ask the
        # user to reopen rather than relaunching ourselves (a normal double-click
        # is the only launch a one-file exe reliably accepts).
        messagebox.showinfo(
            "Update installed",
            f"Version {info['version']} has been installed.\n\n"
            "The app will close now -- please open it again to use the new version.")
        self.root.destroy()

    # --- the whole look, in one place ----------------------------------------

    def _apply_style(self):
        """Configure ttk.Style once. Every widget of a given type reads from
        here, so this single method controls the appearance of the whole window.
        (Like a shared theme/material: edit here, everything updates.)"""
        self.root.configure(bg=BG)
        style = ttk.Style(self.root)
        style.theme_use("clam")   # a base theme that lets us set our own colours

        style.configure(".", font=FONT, background=BG, foreground=TEXT)
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=TEXT)
        style.configure("TButton", padding=6)
        style.map("TButton",
                  background=[("active", ACCENT)],
                  foreground=[("active", "white")])

        # Tabs across the top.
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", padding=(12, 6))
        style.map("TNotebook.Tab",
                  background=[("selected", ACCENT)],
                  foreground=[("selected", "white")])

        # Tables.
        style.configure("Treeview", rowheight=24,
                        background="white", fieldbackground="white")
        style.configure("Treeview.Heading",
                        font=("Segoe UI", 10, "bold"),
                        background=ACCENT, foreground="white", padding=4)
        style.map("Treeview",
                  background=[("selected", ACCENT)],
                  foreground=[("selected", "white")])

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
        for attr in ("history_patient_box", "visit_patient_box",
                     "followup_patient_box", "sell_patient_box"):
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
        # Shade every other row (the "odd" ones) for readability.
        tree.tag_configure("odd", background=STRIPE)
        return tree

    @staticmethod
    def _fill(tree, rows):
        tree.delete(*tree.get_children())
        for i, row in enumerate(rows):
            # Tag alternate rows so the "odd" ones pick up the stripe colour.
            tree.insert("", "end", values=row, tags=("odd",) if i % 2 else ())

    @staticmethod
    def _status_tags(tree):
        """Give a table two colour tags: red = needs attention now (out / expired),
        yellow = warning (low stock / expiring soon)."""
        tree.tag_configure("red", background="#f5b7b1")
        tree.tag_configure("yellow", background="#f9e79f")

    @staticmethod
    def _fill_coloured(tree, rows):
        """Like _fill, but each row is (values_tuple, tag) where tag is
        'red', 'yellow', or '' for normal."""
        tree.delete(*tree.get_children())
        for values, tag in rows:
            tree.insert("", "end", values=values, tags=(tag,) if tag else ())

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
        self._status_tags(self.stock_table)
        self.stock_table.pack(fill="both", expand=True)
        ttk.Label(frame, text="Red = out of stock    Yellow = low, reorder soon",
                  foreground="#666").pack(anchor="w", pady=(4, 0))
        ttk.Button(frame, text="Refresh", command=self._refresh_stock).pack(pady=6)
        self._refresh_stock()
        return frame

    def _refresh_stock(self):
        rows = []
        for _id, name, unit, on_hand, threshold in current_stock(self.conn):
            if on_hand == 0:
                tag = "red"                       # out of stock
            elif on_hand <= threshold:
                tag = "yellow"                    # at or below reorder point
            else:
                tag = ""
            rows.append(((name, on_hand, unit or "units"), tag))
        self._fill_coloured(self.stock_table, rows)

    # --- Alerts tab ----------------------------------------------------------

    def _alerts_tab(self, parent):
        frame = ttk.Frame(parent, padding=10)
        ttk.Label(frame, text="Expiring soon (within 30 days)", font=BOLD).pack(anchor="w")
        self.expiry_table = self._table(
            frame, ("name", "qty", "expiry", "when"),
            ("Medicine", "Qty", "Expiry", "Status"), (170, 60, 110, 150), height=6)
        self._status_tags(self.expiry_table)
        self.expiry_table.pack(fill="both", expand=True)
        ttk.Label(frame, text="Low on stock", font=BOLD).pack(anchor="w", pady=(10, 0))
        self.low_table = self._table(
            frame, ("name", "on_hand", "threshold"),
            ("Medicine", "On hand", "Reorder at"), (220, 90, 110), height=5)
        self._status_tags(self.low_table)
        self.low_table.pack(fill="both", expand=True)
        ttk.Button(frame, text="Refresh", command=self._refresh_alerts).pack(pady=6)
        self._refresh_alerts()
        return frame

    def _refresh_alerts(self):
        expiry_rows = []
        for name, _batch_id, qty, expiry, days_left in expiring_soon(self.conn, days=30):
            if days_left < 0:
                when, tag = f"EXPIRED {-days_left}d ago", "red"      # already expired
            else:
                when, tag = f"in {days_left}d", "yellow"            # expiring soon
            expiry_rows.append(((name, qty, expiry, when), tag))
        self._fill_coloured(self.expiry_table, expiry_rows)

        low_rows = []
        for name, on_hand, threshold in low_stock(self.conn):
            tag = "red" if on_hand == 0 else "yellow"               # out vs low
            low_rows.append(((name, on_hand, threshold), tag))
        self._fill_coloured(self.low_table, low_rows)

    # --- Record sale tab -----------------------------------------------------

    def _sell_tab(self, parent):
        frame = ttk.Frame(parent, padding=10)
        frame.columnconfigure(2, weight=1)
        frame.rowconfigure(5, weight=1)

        ttk.Label(frame, text="Record a sale", font=BOLD)\
            .grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 4))
        ttk.Label(frame, text="Add each medicine to the sale, then click Complete sale.")\
            .grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 8))

        ttk.Label(frame, text="Medicine:").grid(row=2, column=0, sticky="e", padx=4, pady=2)
        self.sell_medicine_box = ttk.Combobox(
            frame, state="readonly", width=22,
            values=[name for _id, name, _p in self._medicines])
        self.sell_medicine_box.grid(row=2, column=1, sticky="w", padx=4, pady=2)

        ttk.Label(frame, text="Quantity:").grid(row=3, column=0, sticky="e", padx=4, pady=2)
        self.qty_entry = ttk.Entry(frame, width=10)
        self.qty_entry.grid(row=3, column=1, sticky="w", padx=4, pady=2)
        ttk.Button(frame, text="Add to sale", command=self._add_to_basket)\
            .grid(row=3, column=2, sticky="w", padx=4, pady=2)

        ttk.Label(frame, text="Items in this sale:")\
            .grid(row=4, column=0, columnspan=3, sticky="w", pady=(8, 2))
        self.basket = []
        self.basket_table = self._table(
            frame, ("name", "qty"), ("Medicine", "Qty"), (260, 80), height=6)
        self.basket_table.grid(row=5, column=0, columnspan=3, sticky="nsew", pady=2)

        ttk.Button(frame, text="Remove selected item", command=self._remove_from_basket)\
            .grid(row=6, column=0, columnspan=3, sticky="w", pady=(2, 6))

        # Payment: paid now, or owed by a patient (pay later). A pay-later sale
        # must name a patient, because a debt has to belong to someone in the records.
        pay = ttk.Frame(frame)
        pay.grid(row=7, column=0, columnspan=3, sticky="w", pady=(0, 2))
        self.sell_paid = tk.IntVar(value=1)
        ttk.Checkbutton(pay, text="Paid now", variable=self.sell_paid).pack(side="left")
        ttk.Label(pay, text="   If pay later, patient:").pack(side="left")
        self.sell_patient_box = ttk.Combobox(
            pay, state="readonly", width=20,
            values=[name for _id, name in self._patients])
        self.sell_patient_box.pack(side="left", padx=4)
        # A read-only dropdown can't be emptied by typing, so give it a Clear
        # button (in case a patient was picked by mistake).
        ttk.Button(pay, text="Clear", width=6,
                   command=lambda: self.sell_patient_box.set("")).pack(side="left")

        ttk.Button(frame, text="Complete sale", command=self._complete_sale)\
            .grid(row=8, column=0, columnspan=3, pady=4)
        self.sell_result = ttk.Label(frame, text="", foreground="green")
        self.sell_result.grid(row=9, column=0, columnspan=3, sticky="w")
        return frame

    def _remove_from_basket(self):
        """Remove the highlighted row from the basket (in case of a mistake)."""
        selected = self.basket_table.selection()
        if not selected:
            self.sell_result.config(text="Pick a row to remove first.", foreground="red")
            return
        # The table rows and self.basket are in the same order, so remove by index.
        index = self.basket_table.index(selected[0])
        del self.basket[index]
        self.basket_table.delete(selected[0])
        self.sell_result.config(text="Item removed.", foreground="green")

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
        paid = bool(self.sell_paid.get())
        patient_id = None
        if not paid:
            index = self.sell_patient_box.current()
            if index < 0:
                self.sell_result.config(
                    text="A pay-later sale needs a patient (they must be in the records).",
                    foreground="red")
                return
            patient_id = self._patients[index][0]

        sale_id, shortfalls = record_sale(self.conn, self.basket,
                                          paid=paid, patient_id=patient_id)
        if sale_id is None:
            message = "Nothing could be sold (out of stock)."
        else:
            total = self.conn.execute(
                "SELECT SUM(quantity * unit_price) FROM sale_items WHERE sale_id = ?",
                (sale_id,)).fetchone()[0]
            message = f"Recorded sale #{sale_id}, total {total}."
            if not paid:
                message += f"  OWED by {self.sell_patient_box.get()}."
        if shortfalls:
            message += f" ({len(shortfalls)} item(s) short)"

        # Reset the basket and payment inputs for the next sale.
        self.basket = []
        self.basket_table.delete(*self.basket_table.get_children())
        self.sell_paid.set(1)
        self.sell_patient_box.set("")
        self._refresh_stock()
        self._refresh_money()
        if hasattr(self, "debts_table"):
            self._refresh_debts()
        self.sell_result.config(text=message, foreground="green")

    # --- Follow-ups tab ------------------------------------------------------

    def _followups_tab(self, parent):
        frame = ttk.Frame(parent, padding=10)
        ttk.Label(frame, text="Scheduled follow-ups", font=BOLD).pack(pady=6)
        ttk.Label(frame,
                  text="All open follow-ups. 'DUE' means the medicine should have run out -- call them.")\
            .pack(anchor="w")
        self.followups_table = self._table(
            frame, ("patient", "phone", "medicine", "runout", "status"),
            ("Patient", "Phone", "Medicine", "Runs out", "Status"),
            (140, 120, 120, 100, 120))
        self.followups_table.pack(fill="both", expand=True, pady=(4, 0))
        ttk.Button(frame, text="Refresh", command=self._refresh_followups).pack(pady=6)
        self._refresh_followups()
        return frame

    def _refresh_followups(self):
        rows = []
        for _fid, patient, phone, medicine, run_out, days_overdue in open_follow_ups(self.conn):
            if days_overdue > 0:
                status = f"DUE ({days_overdue}d ago)"
            elif days_overdue == 0:
                status = "DUE today"
            else:
                status = f"in {-days_overdue}d"
            rows.append((patient, phone or "", medicine or "-", run_out, status))
        self._fill(self.followups_table, rows)

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
        frame.rowconfigure(1, weight=1)
        frame.columnconfigure(0, weight=1)

        header = ttk.Frame(frame)
        header.grid(row=0, column=0, sticky="w", pady=(0, 6))
        ttk.Label(header, text="Report", font=BOLD).pack(side="left")

        # Month or Day: the choice decides which report is built and what the
        # date box should contain.
        self.report_mode = tk.StringVar(value="month")
        ttk.Radiobutton(header, text="Month", variable=self.report_mode,
                        value="month", command=self._report_mode_changed).pack(side="left", padx=(10, 0))
        ttk.Radiobutton(header, text="Day", variable=self.report_mode,
                        value="day", command=self._report_mode_changed).pack(side="left")

        self.report_period = ttk.Entry(header, width=11)
        self.report_period.insert(0, date.today().strftime("%Y-%m"))
        self.report_period.pack(side="left", padx=4)
        ttk.Button(header, text="Show", command=self._refresh_money).pack(side="left", padx=4)
        ttk.Button(header, text="Save report...", command=self._save_report).pack(side="left", padx=4)
        self._help_button(header, "About this report", (
            "MONEY IN counts what was sold, split between sales made during "
            "patient visits and walk-in counter sales.\n\n"
            "MONEY OUT (reorder spend) is cash paid to BUY stock received in "
            "this period.\n\n"
            "COST OF GOODS SOLD is different: it is what the stock actually "
            "SOLD in this period had cost. You might buy a big batch one month "
            "and sell it over many months, so the two numbers differ on "
            "purpose.\n\n"
            "GROSS PROFIT = revenue minus cost of goods sold."
        )).pack(side="left", padx=4)

        # A scrollable, read-only text area holds the report (monospace so the
        # columns line up).
        text_frame = ttk.Frame(frame)
        text_frame.grid(row=1, column=0, sticky="nsew")
        self.report_text = tk.Text(text_frame, wrap="none", font=("Consolas", 10),
                                   background="white", height=20, width=54)
        scroll = ttk.Scrollbar(text_frame, command=self.report_text.yview)
        self.report_text.configure(yscrollcommand=scroll.set)
        # Styles for the report: a centred bold title, coloured section headings,
        # and bold key numbers so the important figures stand out.
        self.report_text.tag_configure("title", justify="center", spacing3=6,
                                       font=("Segoe UI", 14, "bold"), foreground=ACCENT)
        self.report_text.tag_configure("subtitle", justify="center", spacing3=8,
                                       font=("Segoe UI", 10), foreground="#666")
        self.report_text.tag_configure("section", spacing1=6, spacing3=2,
                                       font=("Consolas", 11, "bold"), foreground=ACCENT)
        self.report_text.tag_configure("key", font=("Consolas", 10, "bold"))
        self.report_text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        self.report_status = ttk.Label(frame, text="", foreground="green")
        self.report_status.grid(row=2, column=0, sticky="w", pady=4)

        self._last_report = ""
        self._refresh_money()
        return frame

    def _report_mode_changed(self):
        """Swap the date box content to match the chosen mode (month or day)."""
        self.report_period.delete(0, "end")
        if self.report_mode.get() == "month":
            self.report_period.insert(0, date.today().strftime("%Y-%m"))
        else:
            self.report_period.insert(0, date.today().isoformat())
        self._refresh_money()

    def _refresh_money(self):
        """Build the report for the chosen month or day and show it."""
        period = self.report_period.get().strip()
        if self.report_mode.get() == "month":
            if not _looks_like_month(period):
                self.report_status.config(text="Month must look like YYYY-MM.", foreground="red")
                return
            self._last_report = monthly_report_text(self.conn, period)
        else:
            if not _looks_like_date(period):
                self.report_status.config(text="Day must look like YYYY-MM-DD.", foreground="red")
                return
            self._last_report = daily_report_text(self.conn, period)
        self.report_text.configure(state="normal")
        self.report_text.delete("1.0", "end")
        self.report_text.insert("1.0", self._last_report)
        self._style_report()
        self.report_text.configure(state="disabled")   # read-only
        self.report_status.config(text="", foreground="green")

    # Key figures to make bold in the report, so they stand out from the rest.
    _REPORT_KEY_LINES = ("Revenue received:", "Still owed", "Total if all paid:",
                         "Total owed:", "Gross profit:")

    def _style_report(self):
        """Apply the tags (title, section headings, key numbers) to the report
        text now showing. The saved .txt file stays plain; only the on-screen
        view is styled."""
        for i, line in enumerate(self._last_report.split("\n")):
            span = (f"{i + 1}.0", f"{i + 1}.end")
            if i == 0:
                self.report_text.tag_add("title", *span)           # report name
            elif i == 1:
                self.report_text.tag_add("subtitle", *span)        # the period
            elif line and not line.startswith(" "):
                self.report_text.tag_add("section", *span)         # MONEY IN, etc.
            elif any(key in line for key in self._REPORT_KEY_LINES):
                self.report_text.tag_add("key", *span)             # important numbers

    def _save_report(self):
        """Let the owner save the current report as a text file to keep/read later."""
        period = self.report_period.get().strip()
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            initialfile=f"clinic-report-{period}.txt",
            filetypes=[("Text file", "*.txt"), ("All files", "*.*")])
        if not path:
            return   # the owner cancelled the dialog
        with open(path, "w", encoding="utf-8") as report_file:
            report_file.write(self._last_report)
        self.report_status.config(text=f"Saved to {path}", foreground="green")

    # --- Debts tab -----------------------------------------------------------

    def _debts_tab(self, parent):
        frame = ttk.Frame(parent, padding=10)
        ttk.Label(frame, text="Money owed (pay later)", font=BOLD).pack(pady=6)
        ttk.Label(frame, text="Sales not yet paid. Select one and mark it paid when the patient settles up.")\
            .pack(anchor="w")
        self.debts_table = self._table(
            frame, ("who", "amount", "date"),
            ("Patient", "Amount owed", "Sale date"), (200, 110, 160))
        self.debts_table.pack(fill="both", expand=True, pady=(4, 0))
        self._debt_sale_ids = []   # sale id per table row, in order

        buttons = ttk.Frame(frame)
        buttons.pack(pady=6)
        ttk.Button(buttons, text="Mark selected as paid", command=self._mark_debt_paid).pack(side="left", padx=4)
        ttk.Button(buttons, text="Refresh", command=self._refresh_debts).pack(side="left", padx=4)
        self.debts_result = ttk.Label(frame, text="", foreground="green")
        self.debts_result.pack(anchor="w")
        self._refresh_debts()
        return frame

    def _refresh_debts(self):
        self._debt_sale_ids = []
        rows = []
        for sale_id, sale_datetime, who, amount in outstanding_debts(self.conn):
            self._debt_sale_ids.append(sale_id)
            rows.append((who, amount, sale_datetime))
        self._fill(self.debts_table, rows)

    def _mark_debt_paid(self):
        selected = self.debts_table.selection()
        if not selected:
            self.debts_result.config(text="Select a debt first.", foreground="red")
            return
        index = self.debts_table.index(selected[0])
        sale_id = self._debt_sale_ids[index]
        mark_sale_paid(self.conn, sale_id)
        self._refresh_debts()
        self._refresh_money()
        self.debts_result.config(text=f"Sale #{sale_id} marked as paid.", foreground="green")

    # --- Add medicine tab ----------------------------------------------------

    def _add_medicine_tab(self, parent):
        frame = ttk.Frame(parent, padding=10)
        ttk.Label(frame, text="Add a medicine to the catalog", font=BOLD)\
            .grid(row=0, column=0, columnspan=2, pady=6, sticky="w")

        self.med_fields = {}
        row = 1

        def entry_row(key, label):
            nonlocal row
            ttk.Label(frame, text=label + ":").grid(row=row, column=0, sticky="e", padx=4, pady=2)
            widget = ttk.Entry(frame, width=26)
            widget.grid(row=row, column=1, sticky="w", padx=4, pady=2)
            self.med_fields[key] = widget
            row += 1

        def combo_row(key, label, options):
            # Editable combobox: shows the common choices, but any text is allowed.
            nonlocal row
            ttk.Label(frame, text=label + ":").grid(row=row, column=0, sticky="e", padx=4, pady=2)
            widget = ttk.Combobox(frame, width=24, values=list(options))
            widget.grid(row=row, column=1, sticky="w", padx=4, pady=2)
            self.med_fields[key] = widget
            row += 1

        entry_row("name", "Name *")
        combo_row("form", "Form", COMMON_FORMS)     # shape: tablet, syrup, ...
        combo_row("unit", "Unit", COMMON_UNITS)     # how you count/sell it
        # "?" explains form vs unit, since the difference can be confusing.
        self._help_button(frame, "Form vs Unit", (
            "FORM is the medicine's physical shape: tablet, capsule, syrup, "
            "cream...\n\n"
            "UNIT is how you count and sell it: by the tablet, by the bottle, "
            "by the box...\n\n"
            "For pills they are usually the same word. For liquids they "
            "differ: a cough syrup's form is 'syrup' but you sell it by the "
            "'bottle'.")).grid(row=row - 1, column=2, sticky="w", padx=2)
        entry_row("strength", "Strength")
        entry_row("category", "Category")
        entry_row("unit_price", "Price")
        entry_row("reorder_threshold", "Reorder at")

        self.med_partial = tk.IntVar(value=1)
        ttk.Checkbutton(frame, text="Allow partial sale", variable=self.med_partial)\
            .grid(row=row, column=1, sticky="w", padx=4, pady=2)
        self._help_button(frame, "Allow partial sale", (
            "If a customer asks for more than is in stock:\n\n"
            "TICKED -- sell them the amount that IS in stock (a partial "
            "amount), and the seller is told how much was short.\n\n"
            "UNTICKED -- sell none of this medicine in that case. Use this "
            "for medicine that should only be sold in full amounts, such as "
            "a complete course.")).grid(row=row, column=2, sticky="w", padx=2)
        ttk.Button(frame, text="Add medicine", command=self._submit_medicine)\
            .grid(row=row + 1, column=1, sticky="w", padx=4, pady=8)
        self.med_result = ttk.Label(frame, text="", foreground="green")
        self.med_result.grid(row=row + 2, column=0, columnspan=2, sticky="w")
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

        self.patient_fields = {}
        row = 1

        def entry_row(key, label):
            nonlocal row
            ttk.Label(frame, text=label + ":").grid(row=row, column=0, sticky="e", padx=4, pady=2)
            widget = ttk.Entry(frame, width=26)
            widget.grid(row=row, column=1, sticky="w", padx=4, pady=2)
            self.patient_fields[key] = widget
            row += 1

        entry_row("name", "Name *")
        entry_row("date_of_birth", "Date of birth (YYYY-MM-DD)")
        # Sex is a fixed choice, so use a dropdown (blank = not specified).
        ttk.Label(frame, text="Sex:").grid(row=row, column=0, sticky="e", padx=4, pady=2)
        sex_box = ttk.Combobox(frame, state="readonly", width=24,
                               values=["", "Female", "Male", "Other"])
        sex_box.current(0)
        sex_box.grid(row=row, column=1, sticky="w", padx=4, pady=2)
        self.patient_fields["sex"] = sex_box
        row += 1
        entry_row("address", "Address")
        entry_row("phone", "Phone")

        ttk.Button(frame, text="Add patient", command=self._submit_patient)\
            .grid(row=row, column=1, sticky="w", padx=4, pady=8)
        self.patient_result = ttk.Label(frame, text="", foreground="green")
        self.patient_result.grid(row=row + 1, column=0, columnspan=2, sticky="w")
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
        for widget in self.patient_fields.values():
            if isinstance(widget, ttk.Combobox):
                widget.set("")            # a read-only dropdown clears with set()
            else:
                widget.delete(0, "end")
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

        # Give the medicine free, and/or record it as paid now vs owed (pay later).
        self.visit_free = tk.IntVar(value=0)
        ttk.Checkbutton(frame, text="Give medicine free (no charge)",
                        variable=self.visit_free).grid(row=next_row + 2, column=1, sticky="w", padx=4)
        self.visit_paid = tk.IntVar(value=1)
        ttk.Checkbutton(frame, text="Paid now (untick = patient owes, pay later)",
                        variable=self.visit_paid).grid(row=next_row + 3, column=1, sticky="w", padx=4)

        ttk.Button(frame, text="Save visit", command=self._submit_visit)\
            .grid(row=next_row + 4, column=1, sticky="w", padx=4, pady=8)
        self.visit_result = ttk.Label(frame, text="", foreground="green")
        self.visit_result.grid(row=next_row + 5, column=0, columnspan=2, sticky="w")
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
            quantity = int(qty_text)
            if self.visit_free.get():
                medicines = [(medicine_id, quantity, 0.0)]   # price 0 = free
            else:
                medicines = [(medicine_id, quantity)]

        paid = bool(self.visit_paid.get())
        visit_id, sale_id, shortfalls = record_visit(
            self.conn, patient_id, employee_id=employee_id, visit_date=visit_date,
            diagnosis=self.visit_fields["diagnosis"].get().strip() or None,
            treatment=self.visit_fields["treatment"].get().strip() or None,
            medicines=medicines, paid=paid)

        message = f"Recorded visit #{visit_id}."
        if sale_id is not None:
            if self.visit_free.get():
                message += " (medicine given free)"
            elif not paid:
                message += f" (medicine OWED by {self._patients[patient_index][1]})"
            else:
                message += " (medicine sold)"
        if shortfalls:
            message += " -- some medicine was short of stock"
        # Clear the medicine part; keep patient/date for convenience.
        self.visit_qty.delete(0, "end")
        self.visit_medicine_box.current(0)
        self.visit_free.set(0)
        self.visit_paid.set(1)
        self._refresh_stock()
        self._refresh_money()
        if hasattr(self, "debts_table"):
            self._refresh_debts()
        self.visit_result.config(text=message, foreground="green")

    # --- Add follow-up tab ---------------------------------------------------

    def _add_followup_tab(self, parent):
        frame = ttk.Frame(parent, padding=10)
        ttk.Label(frame, text="Add a follow-up (check-in when medicine runs out)", font=BOLD)\
            .grid(row=0, column=0, columnspan=2, pady=6, sticky="w")
        self._help_button(frame, "How the run-out date is estimated", (
            "The expected run-out date is calculated from what you enter:\n\n"
            "    days of supply = quantity given / daily dose\n"
            "    run-out date = start date + days of supply\n\n"
            "Example: 10 tablets at 2 per day = 5 days.\n\n"
            "It is an estimate that assumes the medicine is taken as "
            "directed. The follow-up list shows patients whose estimated "
            "run-out date has passed, so they can be called to check in."))\
            .grid(row=0, column=2, sticky="w", padx=2)

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
    # Tidy up a leftover backup from a previous self-update, if any.
    updater.cleanup_old()
    # First thing on every start: make sure the database and tables exist.
    # On the very first run on a new computer this creates them from scratch.
    ensure_database()
    conn = get_connection(DB_FILE)
    try:
        ClinicGUI(conn).run()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
