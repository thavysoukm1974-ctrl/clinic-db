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

## What comes next (build order)

1. ✅ Schema — the tables. *(draft done — read it, question it, we refine it together)*
2. ⬜ Simple actions: add/find a patient, record a visit, add a medicine + stock batch, record a sale **and decrease stock**.
3. ⬜ Views/alerts: what's expiring soon, what's low on stock.
4. ⬜ Reports: monthly sales, low stock, expiring soon, a patient's visit history.
5. ⬜ A simple user interface — last, and slowly (new territory for me).

We build step 2 onward **together** in Cowork, so I understand each piece before
moving on.

## Still to confirm with my mother

- What does she look up during a normal day? (Each answer points to a report.)
- One computer or several at once? (Decides SQLite vs PostgreSQL timing.)
- Any existing notebook/spreadsheet to import as a starting point?
- **Stock habit:** will she keep a new batch boxed until the current one runs out
  (so only one batch is open at a time)? This keeps the shelf matching the
  database's soonest-expiry-first selling. (See DECISIONS.md #20.)
- **Short-stock rule:** if a customer wants 8 but only 4 are left, does she sell
  the 4, or sell none? Might differ by medicine (e.g. never a partial antibiotic
  course). Current code sells nothing for that item; confirm with her. (#21.)
