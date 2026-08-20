-- ============================================================================
--  Clinic Database — SCHEMA
-- ============================================================================
--  This file defines the TABLES: the shape of the data. It is the heart of the
--  project. Read it top to bottom -- each table has a comment explaining WHY it
--  exists, not just what it holds.
--
--  The system has TWO sides that meet at the `medicines` table:
--
--    PHARMACY SIDE  -- what we stock and sell (medicines, batches, sales)
--    CLINICAL SIDE  -- who we treat and how  (patients, employees, visits)
--
--  `medicines` is the BRIDGE: a medicine can be given during a visit
--  (clinical) and also sold over the counter (pharmacy).
-- ============================================================================


-- ----------------------------------------------------------------------------
--  IMPORTANT: turn foreign keys ON.
--  SQLite does NOT enforce foreign keys unless you ask it to, once per
--  connection. If you forget, the database will let you create a sale line that
--  points to a medicine that doesn't exist. Our Python runs this same PRAGMA
--  every time it connects (see scripts/init_db.py:get_connection).
-- ----------------------------------------------------------------------------
PRAGMA foreign_keys = ON;


-- ############################################################################
--  PHARMACY SIDE
-- ############################################################################

-- ----------------------------------------------------------------------------
--  SUPPLIERS  (optional / can stay nearly empty for now)
--  Where new stock comes from. Each batch was bought from someone; later you
--  may want "who do I reorder from". supplier_id on a batch is optional, so you
--  can ignore this table until you need it.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS suppliers (
    id      INTEGER PRIMARY KEY,        -- SQLite auto-fills this (rowid)
    name    TEXT    NOT NULL,
    phone   TEXT,
    note    TEXT
);


-- ----------------------------------------------------------------------------
--  MEDICINES  (the catalog -- the BRIDGE between both sides)
--  One row per PRODUCT: e.g. "Paracetamol 500mg tablet". This is the price
--  list. It does NOT track how many you have -- that's the batches table.
--  "What CAN we sell/give" here; "what do we HAVE" in batches.
--
--  Two columns are worth understanding, because they answer a real question --
--  "how do we measure a medicine when some are pills and some are liquid?":
--
--    unit     = HOW WE COUNT/SELL this medicine ("tablet", "bottle", "box").
--               Each medicine declares its own. This is what `quantity` in
--               batches and sale_items counts, and what `unit_price` is per.
--               We do NOT force weight on everything -- you count pills by the
--               piece and syrup by the bottle.
--
--    strength = the "500mg" or "125mg/5ml" printed on the label. It only
--               IDENTIFIES the product (500mg vs 650mg are different rows); we
--               never do arithmetic with it. It is OPTIONAL -- a bandage or a
--               thermometer has no strength, and that's fine.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS medicines (
    id                  INTEGER PRIMARY KEY,
    name                TEXT    NOT NULL,          -- "Paracetamol"
    form                TEXT,                      -- physical type: "tablet", "syrup"
    unit                TEXT,                      -- how we COUNT it: "tablet", "bottle"
    strength            TEXT,                      -- label dose: "500mg" (optional)
    category            TEXT,                      -- "painkiller", "antibiotic" (plain text for now)
    unit_price          REAL    NOT NULL DEFAULT 0,-- current SELLING price per unit
    reorder_threshold   INTEGER DEFAULT 0,         -- warn when total stock drops below this
    is_active           INTEGER NOT NULL DEFAULT 1, -- 1 = sold, 0 = hidden/discontinued.
                                                    --  We flag, not DELETE, so old sales
                                                    --  that reference it still make sense.
    allow_partial_sale  INTEGER NOT NULL DEFAULT 1  -- may this be sold in a smaller
                                                    --  amount than asked when stock is
                                                    --  short? 1 = yes (sell what's left),
                                                    --  0 = no (sell all-or-none of the line).
                                                    --  Default 1 matches the shop's normal
                                                    --  habit: give what is in stock now. The
                                                    --  flag lets specific medicines be marked
                                                    --  no-partial if the owner decides (a
                                                    --  medical judgement -- e.g. some may not
                                                    --  want a partial antibiotic course).
);


-- ----------------------------------------------------------------------------
--  BATCHES  (stock / lots)
--  One row per LOT of a medicine you received. We track stock by batch -- not
--  as a single number on the medicine -- because MEDICINES EXPIRE. The same
--  paracetamol bought in January and June are two batches, two expiry dates,
--  often two buy prices. `quantity` here is "how many are LEFT in this lot".
--  Selling reduces it; at 0 the batch is used up.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS batches (
    id              INTEGER PRIMARY KEY,
    medicine_id     INTEGER NOT NULL,            -- which product this lot is
    supplier_id     INTEGER,                     -- who we bought it from (optional)
    quantity        INTEGER NOT NULL,            -- units REMAINING in this batch
    purchase_price  REAL,                        -- what WE paid per unit (cost)
    received_date   TEXT,                        -- ISO text "2026-08-19"
    expiry_date     TEXT,                        -- ISO text "2027-03-01"

    FOREIGN KEY (medicine_id) REFERENCES medicines(id),
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
);


-- ############################################################################
--  CLINICAL SIDE
-- ############################################################################

-- ----------------------------------------------------------------------------
--  PATIENTS
--  The people the clinic treats. We store DATE OF BIRTH, not age, so age stays
--  correct as years pass (age = today - date_of_birth, computed when needed).
--  NOTE what is NOT here: diagnosis and treatment. Those belong to a VISIT,
--  not a patient -- see the visits table for why.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS patients (
    id              INTEGER PRIMARY KEY,
    name            TEXT    NOT NULL,
    date_of_birth   TEXT,                        -- ISO text; compute age from this
    sex             TEXT,                        -- often medically relevant
    address         TEXT,
    phone           TEXT
);


-- ----------------------------------------------------------------------------
--  EMPLOYEES  (doctors, nurses, pharmacy, lab)
--  One table for all staff. `role` is a FIELD, not four separate tables --
--  simpler to build and explain, and easy to filter ("all doctors"). "lab" is
--  just a role here; the lab does not store results in this version.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS employees (
    id              INTEGER PRIMARY KEY,
    name            TEXT    NOT NULL,
    role            TEXT,                        -- "doctor", "nurse", "pharmacy", "lab"
    date_of_birth   TEXT,
    address         TEXT,
    phone           TEXT
);


-- ----------------------------------------------------------------------------
--  VISITS  (the heart of the clinical side)
--  One row per time a patient is seen. THIS is where diagnosis and treatment
--  live -- NOT on the patient. Why: a patient returns many times with
--  different problems. Put diagnosis on the patient and the next visit
--  overwrites it; put it on the visit and each patient naturally builds a
--  HISTORY. A visit wires together a patient, the doctor who saw them, and a date.
--
--  A visit is never FORCED to have a sale. A patient can be seen and buy
--  nothing (stock ran out, or nothing was needed) -- that's a visit with no
--  sale. But when the clinic DOES give medicine during a visit, that counts as
--  selling it, so a `sales` row can point back here (see sales.visit_id). The
--  link is optional, one-directional, and never required.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS visits (
    id              INTEGER PRIMARY KEY,
    patient_id      INTEGER NOT NULL,            -- who was seen
    employee_id     INTEGER,                     -- which doctor saw them (optional)
    visit_date      TEXT    NOT NULL,            -- ISO text
    diagnosis       TEXT,                        -- what was found, THIS visit
    treatment       TEXT,                        -- what was advised, THIS visit

    FOREIGN KEY (patient_id)  REFERENCES patients(id),
    FOREIGN KEY (employee_id) REFERENCES employees(id)
);


-- ############################################################################
--  SALES  (pharmacy side -- optionally linked back to a visit)
-- ############################################################################
--
--  NOTE: there is no separate "prescription" table. In this clinic, giving
--  medicine to a patient during a visit COUNTS AS SELLING it, so the medicine
--  handed over is recorded once, as a normal sale, with the sale pointing back
--  to its visit. Recording it twice (a prescription AND a sale) would let the
--  two copies drift apart -- so we keep a single source of truth: the sale.
--  To see what a patient was given in a visit, join visit -> sale -> sale_items.

-- ----------------------------------------------------------------------------
--  SALES  (one row per transaction / receipt)
--  A single trip to the counter, or the medicines given during one visit.
--
--  visit_id: which visit this sale belongs to, or NULL for a walk-in counter
--  sale with no visit. This is how "medicine given during diagnosis" is tied to
--  the patient -- optionally, never forced.
--
--  Notice there is NO stored total here. The guiding rule is "record each small
--  event, COMPUTE the summaries": the total is added up from this sale's
--  sale_items whenever it is needed. That way the total can never drift from the
--  lines, and no monthly/weekly total is stored anywhere -- every report is
--  computed from the raw sales.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sales (
    id              INTEGER PRIMARY KEY,
    sale_datetime   TEXT    NOT NULL,            -- ISO text "2026-08-19 14:30:00"
    visit_id        INTEGER,                     -- the visit this sale came from (optional)

    FOREIGN KEY (visit_id) REFERENCES visits(id)
);


-- ----------------------------------------------------------------------------
--  SALE_ITEMS  (the line items inside a sale)
--  One row per medicine on a receipt -- the table that connects SALES to
--  MEDICINES: "sale #12 included 2 boxes of paracetamol at 5.00 each". One sale
--  has many sale_items (a sale has many medicines; a medicine appears in many
--  sales -- a many-to-many resolved with this middle table).
--
--  WHY store unit_price here again instead of reading medicines.unit_price?
--  Because prices CHANGE. Last year's receipt must still show last year's
--  price. We freeze it here at sale time.
--
--  batch_id records WHICH lot the units came from, so stock math and expiry
--  stay honest. It is nullable so a simple sale can leave it empty when it does
--  not need to track the exact batch.
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
--  columns we search/join by most. Safe to ignore while learning; they change
--  nothing about correctness, only speed.
-- ----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_batches_medicine    ON batches(medicine_id);
CREATE INDEX IF NOT EXISTS idx_batches_expiry      ON batches(expiry_date);
CREATE INDEX IF NOT EXISTS idx_saleitems_sale      ON sale_items(sale_id);
CREATE INDEX IF NOT EXISTS idx_saleitems_medicine  ON sale_items(medicine_id);
CREATE INDEX IF NOT EXISTS idx_visits_patient      ON visits(patient_id);
CREATE INDEX IF NOT EXISTS idx_sales_visit         ON sales(visit_id);
