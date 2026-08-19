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
| 5 | **Store `total_amount` on `sales` as a snapshot** | We *could* recompute it by summing `sale_items` every time. Storing it is simpler to read and gives a fixed record of the receipt. Trade-off: it could drift from the lines if we edit a sale — so we treat a finished sale as final. |
| 6 | **`category` is plain text on `medicines`, not its own table (for now)** | Simpler to start and easier to explain. A separate `categories` table would prevent typos ("painkiller" vs "pain killer") and allow renaming in one place — we'll revisit if the category list grows or gets messy. |
| 7 | **Flag `is_active` instead of DELETING a medicine** | Old sales point to the medicine. If we deleted it, past receipts would reference a missing product. Hiding it (is_active = 0) keeps history intact. |
| 8 | **Dates stored as ISO text ("2026-08-19")** | SQLite has no real date type. ISO text sorts correctly (bigger date = bigger string) and SQLite's date functions understand it. Consistent format is the whole trick. |
| 9 | **Foreign keys turned ON in code every connection** | SQLite ignores foreign keys unless you run `PRAGMA foreign_keys = ON` per connection. We put that in one shared `get_connection()` helper so we can never forget it. |
| 10 | **Backups from day one, using SQLite's backup API** | I lost data before. A plain file copy can be corrupt mid-write; the backup API copies a safe, consistent snapshot. |
