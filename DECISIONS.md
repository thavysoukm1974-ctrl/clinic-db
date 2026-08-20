# Decision Log

One line per real decision: **what** we decided and **why**. When you present
this project, this file is your script — every choice you can defend is a choice
you understand. Add to it whenever we decide something. Newest at the bottom.

| # | Decision | Why |
|---|----------|-----|
| 1 | **Language: Python** | It's the language I already understand, which serves my "explain it myself" goal. C# deferred — I'd be learning a new language *and* a UI at once. |
| 2 | **Database: SQLite now, PostgreSQL later** | SQLite is built into Python, needs no server, fine for one shop. Move to Postgres only when multiple computers share one live database. Both are SQL, so the design transfers. |
| 3 | **Track stock by BATCH, not a single quantity number** | Medicines expire. The same product bought in January vs June are different lots with different expiry dates; we must tell them apart to warn about expiry and sell oldest-first. |
| 4 | **Freeze `unit_price` on each `sale_item`** | Prices change over time. A past receipt must show the price it was sold at, not today's price. So we copy the price into the sale line instead of reading it from `medicines` later. |
| 5 | ~~Store `total_amount` on `sales`~~ → **REVERSED (#16): do NOT store it; compute from `sale_items`** | Mother's own principle: "record each small event, compute the summaries." Price is already frozen per line, so the total can be summed honestly and can never drift. No monthly/weekly total is stored anywhere either — every report is computed from raw sales. |
| 6 | **`category` is plain text on `medicines`, not its own table (for now)** | Simpler to start and easier to explain. A separate `categories` table would prevent typos ("painkiller" vs "pain killer") and allow renaming in one place — we'll revisit if the category list grows or gets messy. |
| 7 | **Flag `is_active` instead of DELETING a medicine** | Old sales point to the medicine. If we deleted it, past receipts would reference a missing product. Hiding it (is_active = 0) keeps history intact. |
| 8 | **Dates stored as ISO text ("2026-08-19")** | SQLite has no real date type. ISO text sorts correctly (bigger date = bigger string) and SQLite's date functions understand it. Consistent format is the whole trick. |
| 9 | **Foreign keys turned ON in code every connection** | SQLite ignores foreign keys unless you run `PRAGMA foreign_keys = ON` per connection. We put that in one shared `get_connection()` helper so we can never forget it. |
| 10 | **Backups from day one, using SQLite's backup API** | I lost data before. A plain file copy can be corrupt mid-write; the backup API copies a safe, consistent snapshot. |
| 11 | **Scope grew: pharmacy → full small clinic** (added patients, employees, visits, prescriptions) | Mother's v2 wishlist: the clinic has patients, staff, and clinical visits, not just medicine sales. Added additively — the pharmacy tables were unchanged. `medicines` is the bridge between the pharmacy and clinical sides. |
| 12 | **Diagnosis & treatment live on `visits`, not `patients`** | A patient returns many times with different problems. On the patient, each new visit would overwrite the last; on the visit, each patient builds a real history. |
| 13 | **Employee `role` is a field, not four separate tables** | Doctor/nurse/pharmacy/lab share the same columns. One table with a `role` field is simpler to build, explain, and filter. |
| 14 | **"Lab" is just a staff role — no lab-results table (yet)** | Confirmed with mother: the lab doesn't produce stored results in this version. Revisit only if that changes. |
| 15 | **Visits are NOT linked to sales** | A patient can be seen and buy nothing (stock out, or nothing needed). Forcing a visit to have a sale would make the data lie. `prescription_items` (medicine given in a visit) is optional and separate from `sales`. |
| 16 | **Store `date_of_birth`, not age** | Age changes every year; a stored age silently goes stale. Store the birth date and compute age when needed. |
| 17 | **Added `unit` and `strength` to `medicines`** | `unit` = how we count/sell it (tablet/bottle) — each medicine declares its own, so we don't force weight on everything. `strength` = the label dose ("500mg"), optional and descriptive only; a bandage has none. |
| 18 | **Open question: does giving medicine in a visit also reduce stock?** | Not yet confirmed with mother. For now `prescription_items` records what was given but does not touch `batches`. Decide when we build the stock logic. |
