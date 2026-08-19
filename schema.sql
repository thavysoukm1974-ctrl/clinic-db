-- ============================================================================
--  Clinic (Pharmacy) Database — SCHEMA
-- ============================================================================
--  This file defines the TABLES: the shape of the data. It is the heart of the
--  project. Read it top to bottom -- each table has a comment explaining WHY it
--  exists, not just what it holds.
--
--  How to think about it: the shop has a few core "things" (medicines, stock
--  batches, sales). Each thing is a table. The columns are the facts we know
--  about that thing. The FOREIGN KEYs are the wires that connect them.
--
--  This is a DRAFT. We will refine it together. Nothing here is final.
-- ============================================================================


-- ----------------------------------------------------------------------------
--  IMPORTANT: turn foreign keys ON.
--  SQLite does NOT enforce foreign keys unless you ask it to, and you must ask
--  once per connection. If you forget, the database will happily let you create
--  a sale line that points to a medicine that doesn't exist. So our Python code
--  runs this same PRAGMA every time it connects (see scripts/init_db.py).
-- ----------------------------------------------------------------------------
PRAGMA foreign_keys = ON;


-- ----------------------------------------------------------------------------
--  SUPPLIERS  (optional / can stay nearly empty for now)
--  Where new stock comes from. We keep it because each batch of stock was
--  bought from someone, and later you may want "how much do I owe supplier X"
--  or "who do I reorder paracetamol from". supplier_id on a batch is optional,
--  so you can ignore this table entirely until you need it.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS suppliers (
    id          INTEGER PRIMARY KEY,          -- SQLite auto-fills this (rowid)
    name        TEXT    NOT NULL,
    phone       TEXT,
    note        TEXT
);


-- ----------------------------------------------------------------------------
--  MEDICINES  (the catalog)
--  One row per PRODUCT you sell -- e.g. "Paracetamol 500mg tablet".
--  This is the price list / menu. It does NOT track how many you have; that is
--  the job of the batches table below. Think of this as "what CAN we sell",
--  and batches as "what do we actually HAVE on the shelf right now".
--
--  Design principle from the plan: shop-specific data (names, prices,
--  categories) lives HERE as rows entered through the app -- never hardcoded.
--  A second clinic installs the app and types in their own medicines.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS medicines (
    id                  INTEGER PRIMARY KEY,
    name                TEXT    NOT NULL,        -- "Paracetamol 500mg"
    form                TEXT,                    -- "tablet", "syrup", "capsule"...
    category            TEXT,                    -- "painkiller", "antibiotic"...
                                                 --   kept as plain text for now;
                                                 --   see DECISIONS.md for why we
                                                 --   did NOT make a categories table yet.
    unit_price          REAL    NOT NULL DEFAULT 0,  -- current SELLING price per unit
    reorder_threshold   INTEGER DEFAULT 0,       -- warn when total stock drops below this
    is_active           INTEGER NOT NULL DEFAULT 1 -- 1 = sold, 0 = hidden/discontinued.
                                                 --   We flag instead of DELETE so old
                                                 --   sales that reference it still make sense.
);


-- ----------------------------------------------------------------------------
--  BATCHES  (stock / lots)
--  One row per LOT of a medicine that you received. We track stock by batch --
--  not as a single "quantity" number on the medicine -- because MEDICINES
--  EXPIRE. The same paracetamol bought in January and in June are two batches
--  with two different expiry dates, and we must be able to tell them apart to
--  warn about what is expiring and to sell the oldest stock first.
--
--  quantity here means "how many are LEFT in this batch right now". When you
--  sell, this number goes down. When a batch hits 0, it's used up.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS batches (
    id              INTEGER PRIMARY KEY,
    medicine_id     INTEGER NOT NULL,            -- which product this lot is
    supplier_id     INTEGER,                     -- who we bought it from (optional)
    quantity        INTEGER NOT NULL,            -- units REMAINING in this batch
    purchase_price  REAL,                        -- what WE paid per unit (cost)
    received_date   TEXT,                        -- when it arrived  (ISO text "2026-08-19")
    expiry_date     TEXT,                        -- when it expires  (ISO text "2027-03-01")

    -- The wires: a batch must point to a real medicine and (if given) a real supplier.
    FOREIGN KEY (medicine_id) REFERENCES medicines(id),
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
);


-- ----------------------------------------------------------------------------
--  SALES  (one row per transaction / receipt)
--  A single trip to the counter. It groups the line items together and records
--  when it happened. We store total_amount as a snapshot even though we could
--  add it up from sale_items -- see DECISIONS.md for that trade-off.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sales (
    id              INTEGER PRIMARY KEY,
    sale_datetime   TEXT NOT NULL,               -- ISO text, e.g. "2026-08-19 14:30:00"
    total_amount    REAL NOT NULL DEFAULT 0       -- snapshot of the total at sale time
);


-- ----------------------------------------------------------------------------
--  SALE_ITEMS  (the line items inside a sale)
--  One row per medicine on a receipt. This is the table that connects SALES to
--  MEDICINES: "sale #12 included 2 boxes of paracetamol at 5.00 each". One sale
--  has many sale_items. This is a classic "many-to-many, resolved with a middle
--  table" -- a sale has many medicines, a medicine appears in many sales.
--
--  WHY store unit_price here again instead of reading it from medicines?
--  Because prices CHANGE. If paracetamol was 5.00 last year and is 6.00 now,
--  last year's receipt must still say 5.00. We freeze the price at sale time.
--
--  batch_id records WHICH lot the units came out of, so stock math and expiry
--  stay honest. It's nullable for now so early/simple sales don't have to pick
--  a batch until we build that logic together.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sale_items (
    id           INTEGER PRIMARY KEY,
    sale_id      INTEGER NOT NULL,               -- which receipt this line belongs to
    medicine_id  INTEGER NOT NULL,               -- which product was sold
    batch_id     INTEGER,                        -- which lot it came from (optional for now)
    quantity     INTEGER NOT NULL,               -- how many units on this line
    unit_price   REAL    NOT NULL,               -- price PER UNIT, frozen at sale time

    FOREIGN KEY (sale_id)     REFERENCES sales(id),
    FOREIGN KEY (medicine_id) REFERENCES medicines(id),
    FOREIGN KEY (batch_id)    REFERENCES batches(id)
);


-- ----------------------------------------------------------------------------
--  INDEXES  (speed helpers -- not new data, just faster lookups)
--  An index is like the index at the back of a book: it lets the database jump
--  straight to matching rows instead of scanning every row. We add them on the
--  columns we will search/join by most. Safe to ignore while learning; they
--  change nothing about correctness, only speed.
-- ----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_batches_medicine   ON batches(medicine_id);
CREATE INDEX IF NOT EXISTS idx_batches_expiry     ON batches(expiry_date);
CREATE INDEX IF NOT EXISTS idx_saleitems_sale     ON sale_items(sale_id);
CREATE INDEX IF NOT EXISTS idx_saleitems_medicine ON sale_items(medicine_id);
