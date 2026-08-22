# Clinic (Pharmacy) Database

A pharmacy inventory + sales system for my mother's clinic, and my capstone
project. Built in Python + SQLite. The point is not just working code — it's
that I can **explain every part of it**.

> Full background and goals: `../Downloads/clinic-database-plan.md`
> Every design choice and its reason: `DECISIONS.md`

## What's here so far

```
clinic-db/
├── schema.sql          The database design: the TABLES. Read this first — it's the heart.
├── DECISIONS.md        Every real decision and WHY. Your presentation script.
├── README.md           This file.
├── .gitignore          Keeps the database + backups out of git (they're data, not code).
├── scripts/
│   ├── init_db.py      Build the empty database from schema.sql.
│   ├── sample_data.py  Fill it with FAKE data to test with.
│   ├── backup.py       Make a safe timestamped copy of the database.
│   ├── stock.py        See usable stock on hand; list a medicine's sellable batches (FEFO).
│   ├── sales.py        Record a sale: take stock FEFO, freeze price, honour partial rules.
│   ├── alerts.py       Warnings: what's expiring soon, what's low on stock.
│   ├── visits.py       Record a patient visit (+ medicine given); read a patient's history.
│   ├── reports.py      Sales by month, totals for a date range, best sellers, money in/out.
│   ├── followups.py    "Schedule to come back": estimate when given medicine runs out.
│   ├── inventory.py    Data entry: add a medicine, add a supplier, receive stock (a batch).
│   ├── app.py          Text-menu user interface: calls the functions above.
│   └── gui.py          Graphical window (Tkinter): tabs for stock, alerts, sales, follow-ups, history, money.
├── db/                 The live database file lives here (created on first run, not in git).
└── backups/            Timestamped backups land here (not in git).
```

## Getting started

Run these from **inside the `clinic-db` folder**, in order:

```bash
python scripts/init_db.py
```

```bash
python scripts/sample_data.py
```

```bash
python scripts/backup.py
```

After that, open `db/clinic.sqlite` in **DBeaver** to see the tables and rows
visually. (DBeaver → new SQLite connection → point it at that file.)

## The tables, in one breath

Two sides that meet at **medicines** (the bridge):

**Pharmacy side** — what we stock and sell:
- **medicines** — the catalog: what we *can* sell (name, form, unit, strength, price).
- **batches** — the stock: what we *have*, each lot with its own expiry date.
- **sales** — one row per receipt (when + an optional `visit_id`; the total is *computed* from the lines).
- **sale_items** — the lines on a receipt; connects a sale to the medicines sold.
- **suppliers** — who we buy stock from (optional, mostly for later).

**Clinical side** — who we treat:
- **patients** — the people we treat (name, date of birth, etc.).
- **employees** — all staff, with a `role` (doctor/nurse/pharmacy/lab).
- **visits** — one row per time a patient is seen; holds **diagnosis & treatment**.

> Key ideas: diagnosis/treatment live on the **visit**, not the patient — a patient
> visits many times. Giving medicine during a visit **counts as a sale**, so the
> sale points back to its visit (`sales.visit_id`) — there's no separate
> prescription table. A visit is never *forced* to have a sale: a patient can be
> seen and buy nothing.
