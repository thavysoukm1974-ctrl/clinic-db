"""
gui.py -- a first GRAPHICAL window for the clinic system, using Tkinter.

    python scripts/gui.py

Tkinter is Python's built-in GUI toolkit -- nothing to install. This window
shows the current stock in a table with a Refresh button. Like the text menu,
it holds NO business logic: it just calls current_stock() (the function we
already built) and displays what comes back.

If you have built a UMG widget in Unreal, the ideas line up:
  * we create WIDGETS (a table, a button) -- like UMG widgets,
  * we LAY THEM OUT (here with .pack(), instead of dragging on a canvas),
  * we WIRE an event: the button's click runs a function -- like an
    "On Clicked" event in a Blueprint,
  * and an EVENT LOOP keeps the window alive, waiting for the user -- like the
    game loop that keeps ticking. In Tkinter that loop is root.mainloop().
"""

import tkinter as tk
from tkinter import ttk

from init_db import DB_FILE, get_connection
from stock import current_stock


class StockWindow:
    """One window: a heading, a stock table, and a Refresh button."""

    def __init__(self, conn):
        self.conn = conn

        # The top-level window (like the root canvas of a UMG widget).
        self.root = tk.Tk()
        self.root.title("Clinic system - stock")
        self.root.geometry("440x340")   # width x height in pixels

        # A heading label.
        ttk.Label(
            self.root, text="Current stock on hand", font=("Segoe UI", 12, "bold")
        ).pack(pady=8)

        # A TABLE widget (ttk.Treeview) with three columns.
        self.table = ttk.Treeview(
            self.root, columns=("name", "on_hand", "unit"),
            show="headings", height=8,
        )
        self.table.heading("name", text="Medicine")
        self.table.heading("on_hand", text="On hand")
        self.table.heading("unit", text="Unit")
        self.table.column("name", width=200)
        self.table.column("on_hand", width=80, anchor="e")
        self.table.column("unit", width=100)
        self.table.pack(fill="both", expand=True, padx=10)

        # A BUTTON. `command=self.refresh` wires its click to our function --
        # this is the "On Clicked" event.
        ttk.Button(self.root, text="Refresh", command=self.refresh).pack(pady=8)

        # Fill the table once when the window opens.
        self.refresh()

    def refresh(self):
        """Reload stock into the table. Runs at startup and on every Refresh click."""
        # 1. Clear the rows currently shown.
        for row_id in self.table.get_children():
            self.table.delete(row_id)
        # 2. Ask our existing logic for the numbers, add one row per medicine.
        for _id, name, unit, on_hand in current_stock(self.conn):
            self.table.insert("", "end", values=(name, on_hand, unit or "units"))

    def run(self):
        """Show the window and hand control to the event loop until it is closed."""
        self.root.mainloop()


def main():
    conn = get_connection(DB_FILE)
    try:
        StockWindow(conn).run()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
