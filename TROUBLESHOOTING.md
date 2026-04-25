# Troubleshooting & Dev Notes

Problems encountered during development and how they were resolved.
Check here first before debugging unfamiliar errors.

---

## 1. Migration fails: `Incorrect integer value: '' for column '..._id'`

**When it happens:** Changing a `CharField` to a `ForeignKey` on a MySQL 8 database that already has rows with empty strings (`''`) in that column.

**Root cause:** MySQL strict mode rejects empty strings when converting a `VARCHAR` column to `BIGINT` (FK). Django's `AlterField` tries to alter the column type in place; MySQL refuses because `''` is not a valid integer.

**Fix:** Add a `RunPython` (or `RunSQL`) step *before* the `AlterField` in the migration that clears empty strings and makes the column nullable:

```python
def clear_empty_branches(apps, schema_editor):
    schema_editor.execute(
        "ALTER TABLE inventory_inventorymovement MODIFY destination_branch VARCHAR(100) NULL"
    )
    schema_editor.execute(
        "UPDATE inventory_inventorymovement SET destination_branch = NULL WHERE destination_branch = ''"
    )

class Migration(migrations.Migration):
    atomic = False  # required — see issue #3

    operations = [
        migrations.RunPython(clear_empty_branches, migrations.RunPython.noop),
        migrations.AlterField(...),
    ]
```

**Also:** Set `atomic = False` on the migration (see issue #3).

---

## 2. Migration fails: `Table 'inventory_branch' already exists`

**When it happens:** A migration partially ran (e.g., `CreateModel` succeeded, then a later step failed). Django did not record the migration as applied. On the next `migrate` run, it tries to create the table again.

**Fix options:**

**Option A — Drop the orphaned table and re-run:**
```bash
docker exec supply-chain-match-db-1 mysql -u django -pdjangopass supplychain \
  -e "DROP TABLE IF EXISTS inventory_branch;"
```
Then re-run the migration after fixing the underlying failure.

**Option B — Use `SeparateDatabaseAndState` to skip the CREATE (preferred when data exists):**
```python
migrations.SeparateDatabaseAndState(
    database_operations=[],          # skip — table already in DB
    state_operations=[
        migrations.CreateModel(...)  # still update migration state
    ],
),
```
This tells Django: "trust me, the table exists; just update the state."

---

## 3. Migration fails: `Executing DDL statements while in a transaction on databases that can't perform a rollback`

**When it happens:** Using `schema_editor.execute()` with DDL statements (`ALTER TABLE`, etc.) inside a `RunPython` block on a migration that is wrapped in a transaction.

**Root cause:** MySQL does not support transactional DDL. Django's default wraps each migration in a transaction. DDL inside that transaction is prohibited.

**Fix:** Set `atomic = False` on the migration class:

```python
class Migration(migrations.Migration):
    atomic = False
    ...
```

This makes the migration run outside a transaction. Safe for MySQL since MySQL doesn't support DDL rollback anyway.

---

## 4. Migration fails: `Data truncated for column '..._id' at row 1` (after partial rename)

**When it happens:** A `CharField → ForeignKey` `AlterField` partially runs on MySQL. MySQL's non-transactional DDL means the column gets *renamed* (e.g., `destination_branch` → `destination_branch_id`) but the *type change* to `BIGINT` fails because existing rows have non-integer string values (branch names like `"SM Tarlac"`).

**Result:** The column ends up renamed but still `VARCHAR`, and the migration is not recorded as applied. The next `migrate` run sees the wrong column name and fails again.

**How to detect:** Run `DESCRIBE inventory_inventorymovement;` and check if `destination_branch_id` is still `varchar(...)` instead of `bigint`.

**Fix:**
1. Update any `RunPython` / `RunSQL` steps to target the new column name (`destination_branch_id`) since Django already renamed it.
2. Set ALL string values to `NULL` (not just empty strings) — branch name strings can't convert to FK integer IDs.
3. Use `SeparateDatabaseAndState` for the `AlterField`: do the type change manually via `RunSQL` and skip Django's `AlterField` at the DB level:

```python
migrations.SeparateDatabaseAndState(
    database_operations=[
        migrations.RunSQL(
            sql=(
                "ALTER TABLE inventory_inventorymovement "
                "MODIFY COLUMN destination_branch_id BIGINT NULL, "
                "ADD CONSTRAINT inventory_inventorymovement_dest_branch_fk "
                "FOREIGN KEY (destination_branch_id) REFERENCES inventory_branch(id) "
                "ON DELETE SET NULL"
            ),
            reverse_sql=migrations.RunSQL.noop,
        ),
    ],
    state_operations=[
        migrations.AlterField(
            model_name='inventorymovement',
            name='destination_branch',
            field=models.ForeignKey(...),
        ),
    ],
),
```

---

## 5. Seeder breaks after `CharField → ForeignKey` migration

**When it happens:** `seed_data.py` passes raw branch name strings (e.g., `'SM Tarlac'`) directly to `destination_branch=` and `branch=` fields. After the migration these are FK fields that expect `Branch` model instances, not strings.

**Error:** `ValueError: Cannot assign "SM Tarlac": "InventoryMovement.destination_branch" must be a "Branch" instance.`

**Fix:** Update the seeder to:
1. Create `Branch` objects first.
2. Pass `Branch` instances (not strings) to the FK fields.

```python
# Before
InventoryMovement.objects.get_or_create(
    ...
    defaults={'destination_branch': 'SM Tarlac', ...}
)

# After
branch = Branch.objects.get(name='SM Tarlac')
InventoryMovement.objects.get_or_create(
    ...
    defaults={'destination_branch': branch, ...}
)
```

Also update `get_or_create` lookup fields that used `branch='SM Tarlac'` (for `RetailerSales`) to use the Branch instance instead.

---

## 6. `values('destination_branch')` returns PK instead of name after FK change

**When it happens:** Annotated querysets that used `.values('destination_branch')` return the integer PK of the related `Branch` object after the field is changed to a FK. Dashboard charts and report tables show IDs instead of branch names.

**Fix:** Change the `values()` lookup to traverse the relation:

```python
# Before
.values('destination_branch')

# After
.values('destination_branch__name')
```

Update all referencing templates and CSV export functions accordingly:
- Templates: `{{ row.destination_branch }}` → `{{ row.destination_branch__name }}`
- Python: `row['destination_branch']` → `row['destination_branch__name']`

Django templates handle `__` in dict keys correctly via dot notation: `{{ row.destination_branch__name }}` resolves `row['destination_branch__name']`.

---

## General: MySQL credentials (Docker)

```
Host:     db (service name inside Docker network)
Database: supplychain
User:     django
Password: djangopass
Root PW:  rootpassword
```

Run raw SQL:
```bash
docker exec supply-chain-match-db-1 mysql -u django -pdjangopass supplychain -e "YOUR SQL HERE;"
```

Inspect a table:
```bash
docker exec supply-chain-match-db-1 mysql -u django -pdjangopass supplychain -e "DESCRIBE inventory_inventorymovement;"
```
