from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

from inventory.models import Product, InventoryMovement, RetailerSales, UserProfile, AuditLog, Branch


def _log(user, action, obj, changes=''):
    AuditLog.objects.create(
        user=user,
        action=action,
        model_name=obj.__class__.__name__,
        object_id=obj.pk,
        object_repr=str(obj),
        changes=changes,
    )


BRANCH_DATA = [
    ('SM Grand Central',      'Grand Central Mall, Caloocan City'),
    ('SM San Jose Del Monte', 'SM City San Jose Del Monte, Bulacan'),
    ('Savemore Muzon',        'Muzon, San Jose Del Monte, Bulacan'),
    ('SM Tarlac',             'SM City Tarlac, Tarlac City'),
    ('SM Telabastagan',       'SM City Telabastagan, San Fernando, Pampanga'),
    ('Savemore Apalit',       'Apalit, Pampanga'),
]

# (name, sku, category, unit_price, unit)
PRODUCTS_DATA = [
    ('Kangkong',      'VEG-001', 'Leafy Vegetables', 28.00, 'bundle'),
    ('Pechay',        'VEG-002', 'Leafy Vegetables', 35.00, 'bundle'),
    ('Sitaw',         'VEG-003', 'Pod Vegetables',   52.00, 'bundle'),
    ('Ampalaya',      'VEG-004', 'Gourd Vegetables', 45.00, 'kg'),
    ('Kamote Tops',   'VEG-005', 'Leafy Vegetables', 22.00, 'bundle'),
    ('Malunggay',     'VEG-006', 'Leafy Vegetables', 30.00, 'bundle'),
    ('Okra',          'VEG-007', 'Pod Vegetables',   58.00, 'kg'),
    ('Talong',        'VEG-008', 'Fruit Vegetables', 42.00, 'pcs'),
    ('Kalabasa',      'VEG-009', 'Gourd Vegetables', 38.00, 'pcs'),
    ('Kamatis',       'VEG-010', 'Fruit Vegetables', 65.00, 'kg'),
    ('Sibuyas Dahon', 'VEG-011', 'Leafy Vegetables', 48.00, 'bundle'),
    ('Labanos',       'VEG-012', 'Root Vegetables',  32.00, 'pcs'),
]

# (sku, production_qty, batch_number, reference_no)
# Production date: today-5, expiry: today+9 (14-day shelf life for fresh produce)
PRODUCTION_DATA = [
    ('VEG-001', 180, 'BATCH-VEG001-2504', 'PROD-VEG001-2504-01'),
    ('VEG-002', 160, 'BATCH-VEG002-2504', 'PROD-VEG002-2504-01'),
    ('VEG-003', 140, 'BATCH-VEG003-2504', 'PROD-VEG003-2504-01'),
    ('VEG-004', 130, 'BATCH-VEG004-2504', 'PROD-VEG004-2504-01'),
    ('VEG-005', 200, 'BATCH-VEG005-2504', 'PROD-VEG005-2504-01'),
    ('VEG-006', 150, 'BATCH-VEG006-2504', 'PROD-VEG006-2504-01'),
    ('VEG-007', 120, 'BATCH-VEG007-2504', 'PROD-VEG007-2504-01'),
    ('VEG-008', 170, 'BATCH-VEG008-2504', 'PROD-VEG008-2504-01'),
    ('VEG-009', 220, 'BATCH-VEG009-2504', 'PROD-VEG009-2504-01'),
    ('VEG-010', 110, 'BATCH-VEG010-2504', 'PROD-VEG010-2504-01'),
    ('VEG-011', 190, 'BATCH-VEG011-2504', 'PROD-VEG011-2504-01'),
    ('VEG-012', 160, 'BATCH-VEG012-2504', 'PROD-VEG012-2504-01'),
]

# (sku, branch_name, qty, reference_no)
DELIVERIES_DATA = [
    ('VEG-001', 'SM Grand Central',      30, 'DR-2504-VEG001-SMG'),
    ('VEG-001', 'SM San Jose Del Monte', 25, 'DR-2504-VEG001-SJS'),
    ('VEG-001', 'Savemore Muzon',        20, 'DR-2504-VEG001-MUZ'),
    ('VEG-001', 'SM Tarlac',             25, 'DR-2504-VEG001-TAR'),
    ('VEG-001', 'SM Telabastagan',       20, 'DR-2504-VEG001-TEL'),
    ('VEG-001', 'Savemore Apalit',       15, 'DR-2504-VEG001-APL'),

    ('VEG-002', 'SM Grand Central',      25, 'DR-2504-VEG002-SMG'),
    ('VEG-002', 'SM San Jose Del Monte', 20, 'DR-2504-VEG002-SJS'),
    ('VEG-002', 'Savemore Muzon',        20, 'DR-2504-VEG002-MUZ'),
    ('VEG-002', 'SM Tarlac',             20, 'DR-2504-VEG002-TAR'),
    ('VEG-002', 'SM Telabastagan',       15, 'DR-2504-VEG002-TEL'),

    ('VEG-003', 'SM Grand Central',      20, 'DR-2504-VEG003-SMG'),
    ('VEG-003', 'SM San Jose Del Monte', 20, 'DR-2504-VEG003-SJS'),
    ('VEG-003', 'Savemore Muzon',        15, 'DR-2504-VEG003-MUZ'),
    ('VEG-003', 'SM Tarlac',             20, 'DR-2504-VEG003-TAR'),

    ('VEG-004', 'SM Grand Central',      20, 'DR-2504-VEG004-SMG'),
    ('VEG-004', 'SM Tarlac',             15, 'DR-2504-VEG004-TAR'),
    ('VEG-004', 'SM Telabastagan',       20, 'DR-2504-VEG004-TEL'),
    ('VEG-004', 'Savemore Apalit',       15, 'DR-2504-VEG004-APL'),

    ('VEG-005', 'SM Grand Central',      30, 'DR-2504-VEG005-SMG'),
    ('VEG-005', 'SM San Jose Del Monte', 30, 'DR-2504-VEG005-SJS'),
    ('VEG-005', 'Savemore Muzon',        25, 'DR-2504-VEG005-MUZ'),
    ('VEG-005', 'SM Tarlac',             30, 'DR-2504-VEG005-TAR'),
    ('VEG-005', 'SM Telabastagan',       25, 'DR-2504-VEG005-TEL'),
    ('VEG-005', 'Savemore Apalit',       20, 'DR-2504-VEG005-APL'),

    ('VEG-006', 'SM Grand Central',      25, 'DR-2504-VEG006-SMG'),
    ('VEG-006', 'SM San Jose Del Monte', 20, 'DR-2504-VEG006-SJS'),
    ('VEG-006', 'Savemore Muzon',        20, 'DR-2504-VEG006-MUZ'),
    ('VEG-006', 'SM Telabastagan',       20, 'DR-2504-VEG006-TEL'),

    ('VEG-007', 'SM Grand Central',      15, 'DR-2504-VEG007-SMG'),
    ('VEG-007', 'SM Tarlac',             20, 'DR-2504-VEG007-TAR'),
    ('VEG-007', 'Savemore Apalit',       15, 'DR-2504-VEG007-APL'),

    ('VEG-008', 'SM Grand Central',      25, 'DR-2504-VEG008-SMG'),
    ('VEG-008', 'SM San Jose Del Monte', 20, 'DR-2504-VEG008-SJS'),
    ('VEG-008', 'Savemore Muzon',        20, 'DR-2504-VEG008-MUZ'),
    ('VEG-008', 'SM Tarlac',             25, 'DR-2504-VEG008-TAR'),
    ('VEG-008', 'SM Telabastagan',       20, 'DR-2504-VEG008-TEL'),

    ('VEG-009', 'SM Grand Central',      35, 'DR-2504-VEG009-SMG'),
    ('VEG-009', 'SM San Jose Del Monte', 30, 'DR-2504-VEG009-SJS'),
    ('VEG-009', 'Savemore Muzon',        25, 'DR-2504-VEG009-MUZ'),
    ('VEG-009', 'SM Tarlac',             30, 'DR-2504-VEG009-TAR'),
    ('VEG-009', 'SM Telabastagan',       25, 'DR-2504-VEG009-TEL'),
    ('VEG-009', 'Savemore Apalit',       20, 'DR-2504-VEG009-APL'),

    ('VEG-010', 'SM Grand Central',      20, 'DR-2504-VEG010-SMG'),
    ('VEG-010', 'SM San Jose Del Monte', 15, 'DR-2504-VEG010-SJS'),
    ('VEG-010', 'SM Tarlac',             15, 'DR-2504-VEG010-TAR'),

    ('VEG-011', 'SM Grand Central',      30, 'DR-2504-VEG011-SMG'),
    ('VEG-011', 'SM San Jose Del Monte', 25, 'DR-2504-VEG011-SJS'),
    ('VEG-011', 'Savemore Muzon',        20, 'DR-2504-VEG011-MUZ'),
    ('VEG-011', 'SM Tarlac',             25, 'DR-2504-VEG011-TAR'),
    ('VEG-011', 'Savemore Apalit',       20, 'DR-2504-VEG011-APL'),

    ('VEG-012', 'SM Grand Central',      25, 'DR-2504-VEG012-SMG'),
    ('VEG-012', 'SM San Jose Del Monte', 20, 'DR-2504-VEG012-SJS'),
    ('VEG-012', 'Savemore Muzon',        20, 'DR-2504-VEG012-MUZ'),
    ('VEG-012', 'SM Tarlac',             20, 'DR-2504-VEG012-TAR'),
    ('VEG-012', 'SM Telabastagan',       15, 'DR-2504-VEG012-TEL'),
]

# (sku, qty, note)
LOSSES_DATA = [
    ('VEG-001',  5, 'Wilting during warehouse storage — disposed before dispatch', 'warehouse'),
    ('VEG-002',  8, 'Yellowing detected during quality check; exceeded safe shelf life', 'warehouse'),
    ('VEG-007',  6, 'Pest damage found on inspection — batch quarantined and discarded', 'warehouse'),
    ('VEG-010',  4, 'Bruising from improper stacking during inbound transport', 'warehouse'),
    ('VEG-011',  7, 'Spoilage due to cooling unit downtime — 4-hour temperature breach', 'warehouse'),
]

# (sku, branch_name, qty, reference_no, note)
RETURNS_DATA = [
    ('VEG-001', 'SM Grand Central',       5, 'RT-2504-VEG001-SMG', 'Near-expiry Kangkong returned; accepted at warehouse with deduction note'),
    ('VEG-004', 'SM Tarlac',              4, 'RT-2504-VEG004-TAR', 'Partial return — branch overstocked; 4 bundles returned in good condition'),
    ('VEG-008', 'SM San Jose Del Monte',  6, 'RT-2504-VEG008-SJS', 'Unsold Talong returned with signed return slip from branch supervisor'),
    ('VEG-006', 'Savemore Muzon',         3, 'RT-2504-VEG006-MUZ', 'Branch requested pullback — low foot traffic this week'),
]

# (sku, branch_name, qty, note)
BACK_ORDERS_DATA = [
    ('VEG-003', 'Savemore Apalit',  18, 'Branch requested 18 bundles of Sitaw; stock already committed to other branches this cycle'),
    ('VEG-010', 'SM Telabastagan',  12, 'Kamatis harvest volume insufficient for additional delivery — next batch in 3 days'),
    ('VEG-012', 'Savemore Apalit',  15, 'Labanos back order logged; branch confirmed they will wait for next dispatch'),
]

# (sku, branch_name, days_ago, sold_qty, delivery_qty, resolution_status, resolution_note)
# resolution_status: None = leave as pending; 'returned'/'written_off'/'corrected' = mark resolved
RECONCILIATION_DATA = [
    # Kangkong
    ('VEG-001', 'SM Grand Central',      3, 28, 30, None,          ''),
    ('VEG-001', 'SM San Jose Del Monte', 3, 25, 25, None,          ''),
    ('VEG-001', 'SM Tarlac',             4, 22, 25, 'written_off', '3 bundles confirmed expired before sale date; noted by SM Tarlac branch manager'),

    # Pechay
    ('VEG-002', 'SM Grand Central',      3, 25, 25, None,          ''),
    ('VEG-002', 'SM Tarlac',             3, 18, 20, 'returned',    '2 bundles returned to EFP warehouse; return slip RT-2504-VEG002-TAR on file'),
    ('VEG-002', 'SM Telabastagan',       4, 15, 15, None,          ''),

    # Sitaw
    ('VEG-003', 'SM Grand Central',      3, 20, 20, None,          ''),
    ('VEG-003', 'SM San Jose Del Monte', 3, 17, 20, None,          ''),

    # Ampalaya
    ('VEG-004', 'SM Grand Central',      3, 19, 20, 'corrected',   'Branch re-count confirmed 19 sold; original tally was off by 1 — cashier error'),
    ('VEG-004', 'SM Telabastagan',       3, 20, 20, None,          ''),

    # Kamote Tops
    ('VEG-005', 'SM Grand Central',      3, 30, 30, None,          ''),
    ('VEG-005', 'SM San Jose Del Monte', 3, 28, 30, None,          ''),
    ('VEG-005', 'SM Tarlac',             4, 27, 30, 'written_off', '3 bundles damaged due to improper refrigeration at branch cold room'),

    # Malunggay
    ('VEG-006', 'SM Grand Central',      3, 25, 25, None,          ''),
    ('VEG-006', 'SM San Jose Del Monte', 3, 18, 20, None,          ''),

    # Talong
    ('VEG-008', 'SM Grand Central',      3, 24, 25, None,          ''),
    ('VEG-008', 'SM Tarlac',             3, 25, 25, None,          ''),

    # Kalabasa
    ('VEG-009', 'SM Grand Central',      3, 33, 35, 'returned',    '2 pcs returned — over-delivered vs branch shelf capacity; return accepted'),
    ('VEG-009', 'SM San Jose Del Monte', 3, 30, 30, None,          ''),
    ('VEG-009', 'Savemore Muzon',        3, 22, 25, None,          ''),

    # Kamatis
    ('VEG-010', 'SM Grand Central',      3, 20, 20, None,          ''),

    # Sibuyas Dahon
    ('VEG-011', 'SM Grand Central',      3, 28, 30, 'corrected',   'Branch re-tallied; 28 sold confirmed — previous count of 26 was a cashier encoding error'),
    ('VEG-011', 'SM Tarlac',             3, 25, 25, None,          ''),

    # Labanos
    ('VEG-012', 'SM Grand Central',      3, 23, 25, None,          ''),
    ('VEG-012', 'SM Tarlac',             3, 20, 20, None,          ''),
]


class Command(BaseCommand):
    help = 'Clear and reseed the database with realistic EFP sample data'

    def handle(self, *args, **options):
        today = timezone.now().date()

        # ── Clear existing data ────────────────────────────────────────
        self.stdout.write('Clearing existing data...')
        AuditLog.objects.all().delete()
        RetailerSales.objects.all().delete()
        InventoryMovement.objects.all().delete()
        Product.objects.all().delete()
        UserProfile.objects.all().delete()
        User.objects.exclude(is_superuser=True).delete()
        Branch.objects.all().delete()
        self.stdout.write('  Done.')

        superuser = User.objects.filter(is_superuser=True).first()

        # ── Branches ──────────────────────────────────────────────────
        self.stdout.write('Creating branches...')
        branches = {}
        for name, address in BRANCH_DATA:
            branch = Branch.objects.create(name=name, address=address)
            branches[name] = branch
        self.stdout.write(f'  {len(branches)} branches created.')

        # ── Users ─────────────────────────────────────────────────────
        self.stdout.write('Creating users...')
        role_defs = [
            ('warehouse_staff', 'warehouse',  'Maria',  'Santos'),
            ('sales_rep',       'sales',      'Jose',   'Reyes'),
            ('accountant',      'accountant', 'Ana',    'Cruz'),
            ('admin_user',      'admin',      'Pedro',  'Dela Cruz'),
        ]
        users = {}
        for username, role, first, last in role_defs:
            user = User.objects.create_user(
                username=username,
                password='efp2025',
                first_name=first,
                last_name=last,
                email=f'{username}@efp.local',
            )
            UserProfile.objects.create(user=user, role=role)
            users[role] = user
            if superuser:
                _log(superuser, 'create', user, f"role={role}")
        self.stdout.write(f'  {len(users)} users created.')

        warehouse  = users['warehouse']
        sales      = users['sales']
        accountant = users['accountant']

        prod_date = today - timedelta(days=5)
        exp_date  = today + timedelta(days=9)

        # ── Products ──────────────────────────────────────────────────
        self.stdout.write('Creating products...')
        products = {}
        for name, sku, category, unit_price, unit in PRODUCTS_DATA:
            prod = Product.objects.create(
                name=name,
                sku=sku,
                category=category,
                quantity=0,
                unit=unit,
                unit_price=unit_price,
            )
            products[sku] = prod
            _log(warehouse, 'create', prod, f"SKU={sku}")
        self.stdout.write(f'  {len(products)} products created.')

        # ── Production In ─────────────────────────────────────────────
        self.stdout.write('Recording production batches...')
        production_batches = {}
        for sku, qty, batch_no, ref in PRODUCTION_DATA:
            prod = products[sku]
            mv = InventoryMovement.objects.create(
                product=prod,
                movement_type='production_in',
                quantity=qty,
                reference_no=ref,
                batch_number=batch_no,
                production_date=prod_date,
                expiration_date=exp_date,
                note='Initial harvest batch — April 2025 cycle',
                created_by=warehouse,
                loss_location=loss_loc,
            )
            production_batches[sku] = mv
            _log(warehouse, 'create', mv, f"type=production_in, qty={qty}, product={prod}")

        # ── Delivery Out ──────────────────────────────────────────────
        self.stdout.write('Recording deliveries...')
        delivery_count = 0
        delivery_movements = {}
        for sku, branch_name, qty, ref in DELIVERIES_DATA:
            prod   = products[sku]
            branch = branches[branch_name]
            mv = InventoryMovement.objects.create(
                product=prod,
                movement_type='delivery_out',
                quantity=qty,
                destination_branch=branch,
                reference_no=ref,
                note=f'Weekly consignment delivery to {branch_name}',
                source_batch=production_batches[sku],
                created_by=sales,
                back_order_status='pending',
            )
            _log(sales, 'create', mv,
                 f"type=delivery_out, qty={qty}, product={prod}, branch={branch_name}")
            delivery_movements[(sku, branch_name)] = mv
            delivery_count += 1
        self.stdout.write(f'  {delivery_count} deliveries recorded.')

        # ── Loss ──────────────────────────────────────────────────────
        self.stdout.write('Recording losses...')
        for sku, qty, note, loss_loc in LOSSES_DATA:
            prod = products[sku]
            mv = InventoryMovement.objects.create(
                product=prod,
                movement_type='loss',
                quantity=qty,
                note=note,
                source_batch=production_batches[sku],
                source_delivery=delivery_movements.get((sku, branch_name)),
                created_by=warehouse,
            )
            _log(warehouse, 'create', mv, f"type=loss, qty={qty}, product={prod}")

        # ── Return In ─────────────────────────────────────────────────
        self.stdout.write('Recording returns...')
        for sku, branch_name, qty, ref, note in RETURNS_DATA:
            prod   = products[sku]
            branch = branches[branch_name]
            mv = InventoryMovement.objects.create(
                product=prod,
                movement_type='return_in',
                quantity=qty,
                destination_branch=branch,
                reference_no=ref,
                note=note,
                source_batch=production_batches[sku],
                source_delivery=delivery_movements.get((sku, branch_name)),
                created_by=warehouse,
            )
            _log(warehouse, 'create', mv,
                 f"type=return_in, qty={qty}, product={prod}, branch={branch_name}")

        # ── Back Orders ───────────────────────────────────────────────
        self.stdout.write('Recording back orders...')
        for sku, branch_name, qty, note in BACK_ORDERS_DATA:
            prod   = products[sku]
            branch = branches[branch_name]
            mv = InventoryMovement.objects.create(
                product=prod,
                movement_type='back_order',
                quantity=qty,
                destination_branch=branch,
                note=note,
                created_by=sales,
                back_order_status='pending',
            )
            _log(sales, 'create', mv,
                 f"type=back_order, qty={qty}, product={prod}, branch={branch_name}")

        # ── Reconciliation ────────────────────────────────────────────
        self.stdout.write('Recording reconciliation data...')
        recon_count = 0
        now = timezone.now()
        for sku, branch_name, days_ago, sold_qty, delivery_qty, resolution, note in RECONCILIATION_DATA:
            prod      = products[sku]
            branch    = branches[branch_name]
            sales_date = today - timedelta(days=days_ago)

            rec = RetailerSales.objects.create(
                product=prod,
                branch=branch,
                sold_quantity=sold_qty,
                internal_delivery_qty=delivery_qty,
                sales_date=sales_date,
            )

            if resolution:
                rec.resolution_status = resolution
                rec.resolution_note   = note
                rec.resolved_by       = accountant
                rec.resolved_at       = now
                rec.reconciled        = True
                rec.save()

            _log(accountant, 'create', rec,
                 f"branch={branch_name}, product={prod.name}, sold={sold_qty}, "
                 f"delivery={delivery_qty}, discrepancy={rec.discrepancy}")
            recon_count += 1
        self.stdout.write(f'  {recon_count} reconciliation records created.')

        self.stdout.write(self.style.SUCCESS('\nDone. Login credentials:'))
        self.stdout.write('  warehouse_staff / efp2025')
        self.stdout.write('  sales_rep       / efp2025')
        self.stdout.write('  accountant      / efp2025')
        self.stdout.write('  admin_user      / efp2025')
