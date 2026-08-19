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
│   └── backup.py       Make a safe timestamped copy of the database.
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

## The five tables, in one breath

- **medicines** — the catalog: what we *can* sell (name, form, price).
- **batches** — the stock: what we *have*, each lot with its own expiry date.
- **sales** — one row per receipt (when + total).
- **sale_items** — the lines on a receipt; connects a sale to the medicines sold.
- **suppliers** — who we buy stock from (optional, mostly for later).

## What comes next (build order)

1. ✅ Schema — the tables. *(draft done — read it, question it, we refine it together)*
2. ⬜ Simple actions: add a medicine, record a sale **and decrease stock**, view current stock.
3. ⬜ Views/alerts: what's expiring soon, what's low on stock.
4. ⬜ Reports: sales over a period, revenue, best sellers.
5. ⬜ A simple user interface — last, and slowly (new territory for me).

We build step 2 onward **together** in Cowork, so I understand each piece before
moving on.

## Still to confirm with my mother

- What does she look up during a normal day? (Each answer points to a report.)
- One computer or several at once? (Decides SQLite vs PostgreSQL timing.)
- Any existing notebook/spreadsheet to import as a starting point?
