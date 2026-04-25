# Supply Chain Match — CLAUDE.md

## Project Overview

**Client:** Erlienita's Food Products (EFP)
**Purpose:** Inventory & Supply Chain Management System with Stock Reconciliation
**Context:** Demo/prototype for UP Tacloban MGT 186 — not production-deployed
**Course:** Management of Information Systems and Technology, 2nd Sem AY 2025–2026

EFP supplies fresh produce as a consignor for SM Food Retail Group across 6 branches:
SM Grand Central, SM San Jose Del Monte, Savemore Muzon, SM Tarlac, SM Telabastagan, Savemore Apalit.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Django 5.1, Python |
| Database | MySQL 8.4 (via Docker) |
| Frontend | Bootstrap 5.3, Font Awesome 6.5, crispy-forms |
| Dev environment | Docker Compose |
| DB admin | phpMyAdmin (port 8080) |

---

## Running the Project

```bash
# Start everything
docker compose up

# App:        http://localhost:8000
# phpMyAdmin: http://localhost:8080

# Run migrations (inside container)
docker exec supply-chain-match-web-1 python manage.py migrate

# Create superuser
docker exec -it supply-chain-match-web-1 python manage.py createsuperuser

# Django system check
docker exec supply-chain-match-web-1 python manage.py check
```

The default superuser is `root` (no UserProfile). Superusers bypass role checks and have full admin access.

---

## Architecture

```
config/          Django project settings, URLs, WSGI
inventory/
  models.py      Product, InventoryMovement, RetailerSales, AuditLog, UserProfile
  views.py       All views — no class-based views, all function-based
  forms.py       ProductForm, InventoryMovementForm, RetailerSalesForm,
                 UserCreateForm, UserEditForm
  urls.py        All app routes
  admin.py       Admin panel registrations
  templates/
    inventory/   14 templates, all extend base.html
  migrations/    4 migrations (0001–0004)
```

---

## Data Models

### Product
Fields: `name`, `sku` (unique), `category`, `quantity`, `batch_number`,
`production_date`, `expiration_date`, `unit_price`, `created_at`

### InventoryMovement
Fields: `product` (FK), `movement_type`, `quantity`, `destination_branch`,
`reference_no`, `note`, `created_at`, `created_by` (FK User)

Movement types and their stock effect:
- `production_in` → **adds** to `Product.quantity`
- `return_in` → **adds** to `Product.quantity`
- `delivery_out` → **subtracts** from `Product.quantity`
- `loss` → **subtracts** from `Product.quantity`
- `back_order` → **no quantity change** (recorded only)

Stock update is automatic in `InventoryMovement.save()` on new records only.
Editing or deleting a movement does NOT retroactively adjust quantity (known limitation).

### RetailerSales
Fields: `product` (FK), `branch`, `sold_quantity`, `sales_date`,
`internal_delivery_qty`, `discrepancy`, `reconciled`, `created_at`

`discrepancy = internal_delivery_qty - sold_quantity` — auto-calculated on save.
`reconciled = True` automatically when discrepancy is 0.

### AuditLog
Fields: `user` (FK), `action` (create/update/delete), `model_name`,
`object_id`, `object_repr`, `changes` (text), `timestamp`

Logged on: product add/edit/delete, movement create, reconciliation add, user create/edit.

### UserProfile
OneToOne with Django `User`. Roles: `admin`, `warehouse`, `sales`, `accountant`.
Superusers bypass profile checks entirely.

---

## URL Map

| URL | View | Auth |
|---|---|---|
| `/` | dashboard | login required |
| `/products/` | product_list | login required |
| `/products/add/` | product_create | login required |
| `/products/<pk>/edit/` | product_edit | login required |
| `/products/<pk>/delete/` | product_delete | login required |
| `/movements/` | movement_list | login required |
| `/movements/add/` | movement_create | admin, warehouse, sales |
| `/reconciliation/` | reconciliation_list | admin, accountant |
| `/reconciliation/add/` | reconciliation_add | admin, accountant |
| `/reports/` | reports | login required |
| `/reports/export/losses/` | export_losses_csv | login required |
| `/reports/export/deliveries/` | export_deliveries_csv | login required |
| `/reports/export/back-orders/` | export_back_orders_csv | login required |
| `/audit/` | audit_log | admin only |
| `/users/` | user_management | admin only |
| `/users/add/` | user_create | admin only |
| `/users/<pk>/edit/` | user_edit | admin only |
| `/users/<pk>/deactivate/` | user_deactivate | admin only |
| `/users/<pk>/delete/` | user_delete | admin only |
| `/login/` | user_login | public |
| `/logout/` | user_logout | login required |

---

## Completion Status — ~99%

### Done

- [x] Dashboard with KPI cards: total products, low stock count, near-expiry count, total movements
- [x] Low stock alert (< 10 units) on dashboard
- [x] Near-expiry alert (within 7 days) on dashboard
- [x] Product CRUD — create, list with search, edit, delete with confirmation
- [x] Stock movement recording with automatic `Product.quantity` update
- [x] Movement list with filter by type
- [x] Stock reconciliation — retailer sales vs internal delivery, auto-discrepancy calc
- [x] Reports page — loss analysis by product, deliveries by branch, back orders, reconciliation summary
- [x] Audit log — every create/update/delete recorded with user, timestamp, and field-level diff
- [x] Audit log viewer — admin-only, filterable by action and model
- [x] User management — admin can create users and assign roles
- [x] Role-based access — admin-only pages enforced (user management, audit log)
- [x] Auth — login, logout, `@login_required` on all views, `LOGIN_URL` configured
- [x] Flash messages on all create/edit/delete actions
- [x] Timezone set to Asia/Manila
- [x] Superuser access — bypasses profile role checks correctly
- [x] Docker Compose setup with MySQL + phpMyAdmin
- [x] Login page is standalone — no navbar shown when logged out
- [x] Audit log `_diff()` resolves FK fields to human-readable names
- [x] Movement list shows immutability warning banner
- [x] Role-based view guards — reconciliation restricted to `admin`/`accountant`; movement creation restricted to `admin`/`warehouse`/`sales`
- [x] CSV export on reports page — losses, deliveries by branch, back orders (3 separate download buttons)
- [x] User deactivate/activate and delete — admin can toggle `is_active` or permanently delete users (with confirmation). Superusers and self protected.

### Intentionally Skipped — Do NOT implement unless explicitly told to

- **Movement edit/delete** — intentional by design. No void/reverse mechanism.
- **Reconciliation edit** — records locked after entry by design.
- **Data backup** — out of demo scope.
- **Tests** — out of demo scope.

### Known Bugs / Limitations

None remaining.

---

## Potential Improvements

### Short-term (before demo)
- Add a "correction" movement type or a void/reverse mechanism for wrong entries

### Medium-term
- Pagination on all list pages (products, movements, reconciliation, audit log)
- Product-level movement history page (click a product → see all its movements)
- Dashboard chart (bar chart per branch delivery volume) using Chart.js

### Long-term / Production
- Switch `SECRET_KEY` to environment variable (currently hardcoded)
- Add `ALLOWED_HOSTS` restriction (currently `['*']`)
- Move to Gunicorn + Nginx for production serving
- Scheduled database backup (pg_dump / mysqldump + cron or Django-dbbackup)
- Email or SMS notifications for low stock and near-expiry items

---

## Development Notes

- All views are function-based. No CBVs. Keep it consistent.
- `_is_admin(user)` helper in views.py handles both superusers (no profile) and admin-role users.
- `_has_role(user, *roles)` helper checks if user has any of the given roles (superuser always passes).
- `_log(user, action, obj, changes)` is the audit logging helper — call it on every state-changing
  action in views.
- `_diff(form)` extracts changed fields from a bound ModelForm for human-readable audit entries.
- Do not call `InventoryMovement.save()` more than once per record — quantity adjustment runs
  only on `is_new` (pk is None) to prevent double-counting.
- Migrations: 4 total. Run `makemigrations inventory` then `migrate` inside the container after
  any model changes.
