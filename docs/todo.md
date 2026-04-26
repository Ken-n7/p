# EFP System — Remaining Work

Tasks in recommended order. Tackle one at a time.

---

## 1. Discrepancy sign label fix
**Where:** `reconciliation_list.html`
Minor logic issue — a positive discrepancy (delivered > sold) has no label explaining
what it means. Confusing for clients reading the table.
Fix: add a plain-English label or tooltip next to the discrepancy value.

---

## 2. Discrepancy resolution mechanism
**Where:** `models.py`, migration, `views.py`, `urls.py`, `reconciliation_list.html`
Currently a discrepancy stays Pending forever with no way to close it.
In real operations, discrepancies are resolved by one of three ways:
- Branch returns unsold goods → already handled by `return_in` movement
- Goods expired/damaged at branch → needs a written-off status
- Counting error → needs a corrected entry note

Add a resolution status to `RetailerSales`:
- Status choices: `pending`, `returned`, `written_off`, `corrected`
- Resolution note field (text) — required when resolving
- Resolved by (FK User) and resolved at (datetime) — for audit trail
- Admin and accountant can mark a record as resolved from the reconciliation list

---

## 3. Reconciliation confirm page
**Where:** `reconciliation_add` view + new template
Records are permanent but submit straight through with no warning.
Add a confirmation step before saving, similar to product delete.

---

## 4. Reconciliation CSV export
**Where:** `views.py`, `urls.py`, `reports.html`
Losses, deliveries, and back orders all have CSV exports — reconciliation data does not.
Add an export for reconciliation records (date, branch, product, sold, delivered, discrepancy, status).

---

## 5. Sales summary view
**Where:** `views.py`, `urls.py`, new template, sidebar
No view shows aggregated sales data. Add a page showing:
- Total sold per product (all time)
- Total sold per branch (all time)
Accessible to admin and accountant.

---

## 6. Dashboard reconciliation KPIs
**Where:** `dashboard` view + `dashboard.html`
Dashboard shows stock KPIs but nothing about reconciliation status.
Add: total pending reconciliation count and total discrepancy units.

---

## 7. Product movement history
**Where:** `views.py`, `urls.py`, `product_list.html`, new template
Clicking a product should show all its movements (production, deliveries, returns, losses).
Similar to branch_detail but product-centric.

---

## 8. Movement list filters
**Where:** `movement_list` view + `movement_list.html`
Currently only filterable by movement type.
Add: filter by branch, filter by product, search by reference number.

---

## 9. Reconciliation list filters
**Where:** `reconciliation_list` view + `reconciliation_list.html`
No filters at all.
Add: filter by branch, filter by product, filter by status (reconciled/pending), date range.

---

## 10. Audit log date range filter
**Where:** `audit_log` view + `audit_log.html`
Currently only filterable by action type and model.
Add: date from / date to filter.

---

## 11. User profile & password change
**Where:** `views.py`, `urls.py`, `forms.py`, new template, sidebar
Users cannot see their own role or change their own password.
Add a simple profile page accessible to all logged-in users.
