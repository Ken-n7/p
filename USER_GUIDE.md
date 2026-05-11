# EFP Supply Chain — User Guide

**Client:** Erlienita's Food Products (EFP)
**System:** Inventory & Supply Chain Management with Stock Reconciliation
**Branches served:** SM Grand Central, SM San Jose Del Monte, Savemore Muzon, SM Tarlac, SM Telabastagan, Savemore Apalit

---

## Logging In

Go to `http://localhost:8000` and enter your username and password.
Contact your system admin if you don't have an account.

---

## Roles & Access

| Role | Products | Movements | Reconciliation | Reports | Branches | Users | Audit Log |
|---|---|---|---|---|---|---|---|
| **Admin** | Full | Full | Full | Full | Full | Full | View |
| **Warehouse** | View | Production In, Loss | — | View | View | — | — |
| **Sales** | View | Delivery Out | — | View | View | — | — |
| **Accountant** | View | — | Full | Full | View | — | — |

> Admins can record all movement types and access every page.
> Warehouse and Sales cannot access Reconciliation or User Management.
> Accountants cannot record movements.

---

## Dashboard

First page after login. Shows:

- **Total Products** — number of products in the catalog
- **Low Stock** — products with fewer than 10 units remaining
- **Near Expiry** — production batches expiring within 7 days
- **Total Movements** — all recorded stock movements
- **Deliveries by Branch** — bar chart of total units delivered per branch
- **Recent Movements** — last 10 stock movements
- **Pending Reconciliation** — unresolved discrepancy count and total (Admin and Accountant only)

---

## Products

**Sidebar → Products**

Lists all products with stock level, unit, and expiry status. Rows highlighted in yellow = low stock (below 10 units).

**Search:** Type a product name or SKU in the search bar.

**Add a product:** Click **Add Product** (top right).

**View product detail:** Click the product name to see its full movement history, production batches, and (for Admin/Accountant) sales records per branch.

**Edit a product:** Click the pencil icon on the product row.

**Delete a product:** Click the trash icon → confirm on the next page.
> Cannot delete a product that still has stock remaining. First record a Loss to zero it out.

---

## Branches

**Sidebar → Branches**

Lists all SM/Savemore branches with their total delivered quantities and back order counts.

**View branch detail:** Click a branch name to see all movements to that branch and (for Admin/Accountant) its reconciliation records.

**Add / Edit / Delete a branch:** Admin only. Use the buttons on the list or detail page.

---

## Stock Movements

**Sidebar → Movements**

Records every stock change at EFP's warehouse. Movements are **permanent** — they cannot be edited or deleted after saving. To correct a mistake, record a new correcting movement.

### Movement Types

| Type | Who can record | Effect on stock |
|---|---|---|
| **Production In** | Admin, Warehouse | Adds to stock |
| **Delivery Out** | Admin, Sales | Subtracts from stock |
| **Loss** | Admin, Warehouse | Subtracts from stock |

**Record a movement:** Click **Record Movement** (top right) → select the type → fill in the form.

**Filter movements:** Use the dropdowns above the table to filter by type, branch, product, or reference number.

### Production In

Goods produced or harvested by EFP enter the warehouse.

- Batch number and expiration date are required
- Stock effect: **increases**

### Delivery Out

Goods sent from EFP's warehouse to an SM/Savemore branch.

- Branch and reference number (delivery receipt) are required
- Select the source batch to track which batch was dispatched
- Cannot deliver more than what is currently in stock
- Stock effect: **decreases**

### Loss

Goods damaged, spoiled, or lost at EFP's warehouse.

- Record the affected delivery for traceability (optional but recommended)
- Cannot record more loss than what is currently in stock
- Stock effect: **decreases**

---

## Stock Reconciliation

**Sidebar → Reconciliation** *(Admin and Accountant only)*

Compares EFP's internal delivery records against actual sales reported by SM/Savemore branches. EFP operates on consignment — branches only pay for what they sell.

**Discrepancy = Internal Delivery Qty − Sold Qty**

| Discrepancy | Meaning | Status |
|---|---|---|
| 0 | Branch sold exactly what was delivered | Auto-reconciled (green) |
| Positive | Branch sold less than delivered | Pending — needs resolution |

**Add a record:** Click **Add Sales Data** → fill in branch, product, delivery, sold quantity, and sales date → review the confirmation screen → submit.

Records are **locked** after entry. If a figure was entered incorrectly, resolve the record using the options below.

### Resolving a Discrepancy

Click **Resolve** on any pending record. Choose one of:

| Resolution | What it does |
|---|---|
| **Accepted Loss** | Marks the discrepancy as accepted — goods were spoiled, stolen, or otherwise unrecoverable |
| **Returned to EFP** | Marks the goods as physically returned (log a Return In movement separately if needed) |
| **Corrected Entry** | Replaces the sold quantity with a corrected figure — creates a new reconciliation record automatically |

All resolutions are permanent and recorded in the audit log.

---

## Sales Summary

**Sidebar → Consignment Summary** *(Admin and Accountant only)*

Shows aggregate sold and delivered quantities broken down by product and by branch. Useful for reviewing overall consignment performance across all SM/Savemore branches.

---

## Reports

**Sidebar → Reports**

| Section | What it shows |
|---|---|
| **Loss Analysis** | Total units lost per product (warehouse losses + unrecovered discrepancies) |
| **Deliveries by Branch** | Total delivery quantity and movement count per branch |
| **Unreturned / Unsold** | Reconciled records with a positive discrepancy not marked as returned |
| **Back Orders** | Historical back order records (recorded before this feature was removed from the UI) |
| **Reconciliation Summary** | Count of reconciled vs unreconciled records |

**Export to CSV:** Use the three download buttons at the top right — Losses, Deliveries, Back Orders.

---

## User Management *(Admin only)*

**Sidebar → Users**

Shows all system users, their roles, and account status.

**Add a user:** Click **Add User** → fill in username, name, email, password, and assign a role.

**Edit a user:** Click **Edit** on the user row — update name, email, or role.

**Deactivate / Activate:** Prevents or restores login access without deleting the account. Click the toggle button on the user row.

**Delete a user:** Click the trash icon → confirm. Permanently removes the account. Audit log entries from that user are preserved but unlinked.

> You cannot deactivate or delete your own account or any superuser account.

---

## Audit Log *(Admin only)*

**Sidebar → Audit Log**

Full history of every create, update, and delete action — who did it, when, and what changed (field-level diff for edits).

**Filter:** Use the Action, Model, and date range filters to narrow results.

Shows the last 200 entries. Records cannot be modified or deleted.

---

## My Profile

Click your username in the top navigation bar.

- **Edit profile** — update your display name and email address
- **Change password** — enter your current password, then set a new one
