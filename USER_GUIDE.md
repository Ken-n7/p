# EFP Supply Chain — User Guide

## Logging In

Go to `http://localhost:8000` and enter your username and password.
Contact your system admin if you don't have an account.

---

## Roles & Access

| Role | What they can do |
|---|---|
| **Admin** | Full access to everything |
| **Warehouse** | Products, Movements, Dashboard |
| **Sales** | Products, Movements, Dashboard |
| **Accountant** | Products, Reconciliation, Reports, Dashboard |

> Admins also have access to User Management and Audit Log.
> Accountants **cannot** record movements.
> Warehouse and Sales **cannot** access Reconciliation.

---

## Dashboard

The first page after login. Shows:
- **Total Products** — number of products in the catalog
- **Low Stock** — products with less than 10 units remaining
- **Near Expiry** — products expiring within 7 days
- **Total Movements** — all recorded stock movements
- **Deliveries by Branch chart** — bar chart of total units delivered per SM/Savemore branch
- **Recent Movements** — last 10 stock movements

---

## Products

**View products:** Sidebar → Products

Shows all products with stock level, batch number, production/expiry dates, and unit price.
Rows highlighted in yellow = low stock (below 10 units).

**Search:** Type a product name or SKU in the search bar.

**Add a product:** Click **Add Product** (top right).

**Edit a product:** Click the pencil icon on the product row.

**Delete a product:** Click the trash icon → confirm on the next page.
> Warning: deleting a product also deletes all its movement records.

---

## Stock Movements

**View movements:** Sidebar → Movements

Records every change in stock. Movements are **permanent** — they cannot be edited or deleted.
To correct a mistake, record a new correcting movement (e.g. a *Return In* to cancel a wrong *Delivery Out*).

**Movement types:**

| Type | Effect on stock |
|---|---|
| Production In | Adds to stock |
| Return In | Adds to stock |
| Delivery Out | Subtracts from stock |
| Loss | Subtracts from stock |
| Back Order | No stock change (recorded only) |

**Record a movement:** Click **Record Movement** (top right) → fill in product, type, quantity, and destination branch.

**Filter by type:** Use the dropdown above the table.

---

## Stock Reconciliation

**View reconciliation:** Sidebar → Reconciliation *(Admin and Accountant only)*

Compares EFP's internal delivery records against actual sales reported by SM/Savemore branches.

**Discrepancy** = Internal Delivery Qty − Sold Qty
- **0** = Reconciled (green)
- **Negative** = Branch sold less than delivered (red)
- **Positive** = Branch sold more than delivered (amber)

**Add a record:** Click **Add Sales Data** → enter branch, product, sold quantity, and internal delivery quantity.

Records are **permanent** once saved. If incorrect, submit a new corrected entry.

---

## Reports

**View reports:** Sidebar → Reports

Three sections:
- **Loss Analysis by Product** — total units lost per product
- **Deliveries by Branch** — total deliveries and quantities per SM/Savemore branch
- **Back Orders** — all back order movements

**Export to CSV:** Use the three download buttons at the top right (Losses, Deliveries, Back Orders).

---

## User Management *(Admin only)*

**View users:** Sidebar → Users

Shows all system users, their roles, and account status.

**Add a user:** Click **Add User** → fill in username, name, email, password, and assign a role.

**Edit a user:** Click **Edit** on the user row.

**Deactivate / Activate:** Click **Deactivate** to prevent a user from logging in without deleting their account. Click **Activate** to restore access.

**Delete a user:** Click the trash icon → confirm. This permanently removes the account.
Audit log entries from that user are preserved but unlinked.

> You cannot deactivate or delete your own account, or any superuser account.

---

## Audit Log *(Admin only)*

**View audit log:** Sidebar → Audit Log

Shows a history of every create, update, and delete action performed in the system — who did it, when, and what changed.

**Filter:** Use the Action and Model dropdowns to narrow results.

Showing last 200 entries. Records cannot be deleted.
