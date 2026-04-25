# EFP Supply Chain System — User Guide

**Client:** Erlienita's Food Products (EFP)
**System:** Inventory & Supply Chain Management with Stock Reconciliation
**Branches served:** SM Grand Central, SM San Jose Del Monte, Savemore Muzon, SM Tarlac, SM Telabastagan, Savemore Apalit

---

## User Roles

The system has four roles. Each role has a specific scope — users only see and can do what their role permits.

### Admin
Full access to everything in the system.

- Manage products (add, edit, delete)
- Record any type of stock movement
- View and add reconciliation records
- View reports and export CSV files
- Manage users (create, edit, deactivate, delete)
- View the audit log
- Override sequence warnings when entering retroactive or corrective records

### Warehouse Staff
Handles physical stock at EFP's warehouse.

- Record inbound and internal movements:
  - Production In
  - Return In
  - Loss
- View products, movements, and reports

### Sales & Distribution
Handles outbound deliveries to branches.

- Record outbound movements:
  - Delivery Out
  - Back Order
- View products, movements, and reports

### Accountant
Handles financial reconciliation between EFP and SM/Savemore branches.

- Add and view retailer sales data (reconciliation)
- View reports and export CSV files
- Override sequence warnings when entering retroactive or corrective records
- View products and movements (read only)

---

## Movement Types

Stock movements are the core of the system. Every time goods physically move — in or out of EFP's warehouse — a movement record is created. Movements **cannot be edited or deleted** after saving; this is by design to maintain a reliable audit trail.

### Production In
**Who records it:** Warehouse Staff, Admin

Goods produced or harvested by EFP enter the warehouse. This increases the product's stock quantity.

**Example:** EFP harvests 150kg of Kangkong and brings it into the warehouse.

- Branch: not required (goods stay at EFP)
- Reference number: not required
- Stock effect: **increases**

---

### Delivery Out
**Who records it:** Sales & Distribution, Admin

Goods are sent from EFP's warehouse to an SM or Savemore branch for consignment. This decreases the product's stock quantity.

**Example:** EFP delivers 40kg of Pechay to SM Tarlac.

- Branch: **required** (must specify which branch)
- Reference number: **required** (delivery receipt number that the branch signs)
- Stock effect: **decreases**
- Validation: cannot deliver more than what is currently in stock

---

### Return In
**Who records it:** Warehouse Staff, Admin

Unsold goods are sent back from a branch to EFP's warehouse. This increases the product's stock quantity.

**Example:** SM Grand Central returns 8kg of unsold Ampalaya.

- Branch: **required** (must specify which branch returned the goods)
- Reference number: **required** (return slip number accompanying the goods)
- Stock effect: **increases**
- Validation:
  - A prior delivery to that branch must exist for the same product
  - Return quantity cannot exceed what was net delivered to that branch

---

### Loss
**Who records it:** Warehouse Staff, Admin

Goods that were damaged, spoiled, or otherwise lost at EFP's warehouse. This decreases the product's stock quantity.

**Example:** 5kg of Sitaw spoiled during storage before dispatch.

- Branch: not required (loss happens at EFP's warehouse)
- Reference number: not required
- Stock effect: **decreases**
- Validation: cannot record more loss than what is currently in stock

---

### Back Order
**Who records it:** Sales & Distribution, Admin

A branch requested goods but EFP did not have enough stock to fulfill the order. The order is recorded for tracking purposes. **This does not move any stock.**

**Example:** SM Telabastagan requested 30kg of Malunggay but EFP only had 10kg — the shortfall is recorded as a back order.

- Branch: **required** (which branch made the request)
- Reference number: not required
- Stock effect: **none**
- Validation: stock must be insufficient to fulfill the order

---

## Stock Reconciliation

EFP operates on a consignment basis — SM and Savemore branches only pay for what they actually sell. The reconciliation module compares what EFP delivered against what the branch reported selling.

**Fields:**
- **Product** — which product is being reconciled
- **Branch** — which SM/Savemore branch
- **Sales Date** — date the branch reported sales for
- **Sold Quantity** — how many units the branch sold
- **Internal Delivery Quantity** — how many units EFP delivered to that branch

**Discrepancy** is calculated automatically:

```
Discrepancy = Internal Delivery Qty − Sold Quantity
```

- **Positive discrepancy** — branch sold less than delivered (spoilage, theft, or counting error)
- **Zero discrepancy** — branch sold exactly what was delivered (auto-marked as Reconciled)
- **Negative discrepancy** — not allowed; sold quantity cannot exceed delivered quantity

Reconciliation records are locked after entry and cannot be edited.

---

## Admin Override

Admin and Accountant users may encounter **warnings** when entering movements that look unusual but are legitimate. This typically happens when entering records after the fact (e.g., catching up on a backlog).

When a warning appears, a confirmation checkbox is shown at the bottom of the form. Checking the box and resubmitting tells the system the entry is intentional. All overrides are recorded in the audit log.

**Warnings can be overridden:**
- Return In with no prior delivery on record (e.g., delivery not yet entered)
- Back Order when stock appears sufficient (e.g., stock was already committed elsewhere)

**Warnings that cannot be overridden (hard blocks for everyone):**
- Delivering more than current stock
- Returning more than net delivered to that branch
- Recording a loss greater than current stock
- Recording a Production In for an expired product
- Recording a Return In for an expired product

---

## Audit Log

Every create, update, and delete action in the system is recorded automatically with:
- Who performed the action
- What was changed (field-level diff for edits)
- When it happened

The audit log is visible to Admin only and cannot be modified.

---

## Reports & Exports

The Reports page provides summaries of:
- **Loss Analysis** — total losses per product
- **Deliveries by Branch** — total quantity and number of deliveries per branch
- **Back Orders** — list of all unfulfilled orders
- **Reconciliation Summary** — reconciled vs unreconciled record counts

All three main reports can be exported as CSV files for use in Excel or accounting software.
