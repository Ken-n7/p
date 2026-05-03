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
    ('Kangkong',    'VEG-001', 'Leafy Vegetables', 28.00, 'bundle'),
    ('Pechay',      'VEG-002', 'Leafy Vegetables', 35.00, 'bundle'),
    ('Sitaw',       'VEG-003', 'Pod Vegetables',   52.00, 'bundle'),
    ('Ampalaya',    'VEG-004', 'Gourd Vegetables', 45.00, 'kg'),
    ('Kamote Tops', 'VEG-005', 'Leafy Vegetables', 22.00, 'bundle'),
]

# (sku, production_qty, batch_number)
PRODUCTION_DATA = [
    ('VEG-001', 120, 'BATCH-VEG001-2504'),
    ('VEG-002', 100, 'BATCH-VEG002-2504'),
    ('VEG-003',  80, 'BATCH-VEG003-2504'),
    ('VEG-004',  90, 'BATCH-VEG004-2504'),
    ('VEG-005', 150, 'BATCH-VEG005-2504'),
]

# (sku, branch_name, qty, reference_no)
# VEG-003 Savemore Apalit delivery is created separately as part of the back order partial scenario
DELIVERIES_DATA = [
    ('VEG-001', 'SM Grand Central',      30, 'DR-2504-VEG001-SMG'),
    ('VEG-001', 'SM Tarlac',             25, 'DR-2504-VEG001-TAR'),
    ('VEG-001', 'Savemore Muzon',        20, 'DR-2504-VEG001-MUZ'),

    ('VEG-002', 'SM Grand Central',      25, 'DR-2504-VEG002-SMG'),
    ('VEG-002', 'SM San Jose Del Monte', 20, 'DR-2504-VEG002-SJS'),
    ('VEG-002', 'SM Telabastagan',       15, 'DR-2504-VEG002-TEL'),

    ('VEG-003', 'SM Grand Central',      20, 'DR-2504-VEG003-SMG'),
    ('VEG-003', 'SM Tarlac',             18, 'DR-2504-VEG003-TAR'),

    ('VEG-004', 'SM Grand Central',      20, 'DR-2504-VEG004-SMG'),
    ('VEG-004', 'SM Tarlac',             15, 'DR-2504-VEG004-TAR'),

    ('VEG-005', 'SM Grand Central',      30, 'DR-2504-VEG005-SMG'),
    ('VEG-005', 'SM San Jose Del Monte', 25, 'DR-2504-VEG005-SJS'),
    ('VEG-005', 'Savemore Muzon',        20, 'DR-2504-VEG005-MUZ'),
]

# (sku, qty, note, loss_location, transit_branch_or_None)
# transit losses must reference a delivery; warehouse losses have no source_delivery
LOSSES_DATA = [
    ('VEG-001', 5, 'Wilting during warehouse storage — disposed before dispatch',         'warehouse', None),
    ('VEG-002', 3, 'Damaged bundles found during transit to SM Grand Central',             'transit',   'SM Grand Central'),
    ('VEG-005', 4, 'Spoilage due to cooling unit downtime — 4-hour temperature breach',   'warehouse', None),
]

# (sku, branch_name, sold_qty, delivery_qty, days_ago, resolution_status, resolution_note)
# resolution_status None = leave as pending; discrepancy = delivery_qty - sold_qty
RECONCILIATION_DATA = [
    # Kangkong — pending gap, written off, pending gap
    ('VEG-001', 'SM Grand Central',      28, 30, 3, None,          ''),
    ('VEG-001', 'SM Tarlac',             22, 25, 4, 'written_off', '3 bundles confirmed expired before sale date; noted by SM Tarlac branch manager'),
    ('VEG-001', 'Savemore Muzon',        18, 20, 3, None,          ''),

    # Pechay — exact match (auto-reconciled), pending gap
    ('VEG-002', 'SM Grand Central',      25, 25, 3, None,          ''),
    ('VEG-002', 'SM San Jose Del Monte', 17, 20, 4, None,          ''),

    # Sitaw — pending gaps
    ('VEG-003', 'SM Grand Central',      19, 20, 3, None,          ''),
    ('VEG-003', 'SM Tarlac',             18, 18, 3, None,          ''),

    # Ampalaya — corrected entry, exact match
    ('VEG-004', 'SM Grand Central',      19, 20, 3, 'corrected',   'Branch re-count confirmed 19 sold; original tally was off by 1 — cashier encoding error'),
    ('VEG-004', 'SM Tarlac',             15, 15, 3, None,          ''),

    # Kamote Tops — over-sold (negative discrepancy), written off, pending
    ('VEG-005', 'SM Grand Central',      32, 30, 3, 'over_sold',   'Branch re-count showed 32 sold; demand exceeded initial supply — branch miscalculated intake'),
    ('VEG-005', 'SM San Jose Del Monte', 23, 25, 4, 'written_off', '2 bundles damaged due to improper refrigeration at branch cold room'),
    ('VEG-005', 'Savemore Muzon',        18, 20, 3, None,          ''),
]


class Command(BaseCommand):
    help = 'Clear and reseed the database with focused EFP sample data'

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
            branches[name] = Branch.objects.create(name=name, address=address)
        self.stdout.write(f'  {len(branches)} branches created.')

        # ── Users ─────────────────────────────────────────────────────
        self.stdout.write('Creating users...')
        role_defs = [
            ('warehouse_staff', 'warehouse',  'Maria', 'Santos'),
            ('sales_rep',       'sales',      'Jose',  'Reyes'),
            ('accountant',      'accountant', 'Ana',   'Cruz'),
            ('admin_user',      'admin',      'Pedro', 'Dela Cruz'),
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
                name=name, sku=sku, category=category,
                quantity=0, unit=unit, unit_price=unit_price,
            )
            products[sku] = prod
            _log(warehouse, 'create', prod, f"SKU={sku}")
        self.stdout.write(f'  {len(products)} products created.')

        # ── Production In ─────────────────────────────────────────────
        self.stdout.write('Recording production batches...')
        production_batches = {}
        for sku, qty, batch_no in PRODUCTION_DATA:
            prod = products[sku]
            mv = InventoryMovement.objects.create(
                product=prod,
                movement_type='production_in',
                quantity=qty,
                batch_number=batch_no,
                production_date=prod_date,
                expiration_date=exp_date,
                note='Initial harvest batch — April 2025 cycle',
                created_by=warehouse,
            )
            production_batches[sku] = mv
            _log(warehouse, 'create', mv, f"type=production_in, qty={qty}, product={prod}")
        self.stdout.write(f'  {len(production_batches)} batches recorded.')

        # ── Delivery Out ──────────────────────────────────────────────
        self.stdout.write('Recording deliveries...')
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
            )
            delivery_movements[(sku, branch_name)] = mv
            _log(sales, 'create', mv,
                 f"type=delivery_out, qty={qty}, product={prod}, branch={branch_name}")
        self.stdout.write(f'  {len(delivery_movements)} deliveries recorded.')

        # ── Stock Loss ────────────────────────────────────────────────
        self.stdout.write('Recording stock losses...')
        for sku, qty, note, loss_loc, transit_branch in LOSSES_DATA:
            prod = products[sku]
            source_delivery = delivery_movements.get((sku, transit_branch)) if transit_branch else None
            mv = InventoryMovement.objects.create(
                product=prod,
                movement_type='loss',
                quantity=qty,
                note=note,
                loss_location=loss_loc,
                source_batch=production_batches[sku],
                source_delivery=source_delivery,
                created_by=warehouse,
            )
            _log(warehouse, 'create', mv,
                 f"type=loss, qty={qty}, product={prod}, location={loss_loc}")
        self.stdout.write(f'  {len(LOSSES_DATA)} losses recorded.')

        # ── Back Orders ───────────────────────────────────────────────
        self.stdout.write('Recording back orders...')

        # Simple pending back order — insufficient stock this cycle
        bo_kamote = InventoryMovement.objects.create(
            product=products['VEG-005'],
            movement_type='back_order',
            quantity=20,
            destination_branch=branches['SM Telabastagan'],
            note='Branch requested 20 bundles of Kamote Tops; insufficient stock this cycle — next harvest in 3 days',
            created_by=sales,
            back_order_status='pending',
        )
        _log(sales, 'create', bo_kamote,
             "type=back_order, qty=20, product=Kamote Tops, branch=SM Telabastagan, status=pending")

        # Partial fulfillment scenario — Sitaw to Savemore Apalit
        # Step 1: Branch orders 25 bundles; recorded as back order
        bo_sitaw = InventoryMovement.objects.create(
            product=products['VEG-003'],
            movement_type='back_order',
            quantity=25,
            destination_branch=branches['Savemore Apalit'],
            note='Branch requested 25 bundles of Sitaw; stock already committed to other branches this cycle',
            created_by=sales,
            back_order_status='fulfilled',
        )
        _log(sales, 'create', bo_sitaw,
             "type=back_order, qty=25, product=Sitaw, branch=Savemore Apalit, status=fulfilled")

        # Step 2: Only 15 bundles available — partial delivery that closes the back order
        mv_sitaw_partial = InventoryMovement.objects.create(
            product=products['VEG-003'],
            movement_type='delivery_out',
            quantity=15,
            destination_branch=branches['Savemore Apalit'],
            reference_no='DR-2504-VEG003-APL',
            note='Partial fulfillment of back order — 15 of 25 bundles delivered; remainder re-queued',
            source_batch=production_batches['VEG-003'],
            closes_back_order=bo_sitaw,
            created_by=sales,
        )
        delivery_movements[('VEG-003', 'Savemore Apalit')] = mv_sitaw_partial
        _log(sales, 'create', mv_sitaw_partial,
             "type=delivery_out, qty=15, product=Sitaw, branch=Savemore Apalit, closes_back_order=yes")

        # Step 3: Remainder back order auto-created for the unfulfilled 10 bundles
        bo_sitaw_remainder = InventoryMovement.objects.create(
            product=products['VEG-003'],
            movement_type='back_order',
            quantity=10,
            destination_branch=branches['Savemore Apalit'],
            note='Remaining 10 bundles from partial fulfillment of 25-unit back order — next dispatch expected',
            created_by=sales,
            back_order_status='pending',
        )
        _log(sales, 'create', bo_sitaw_remainder,
             "type=back_order, qty=10, product=Sitaw, branch=Savemore Apalit, status=pending")

        self.stdout.write('  3 back orders recorded (1 pending, 1 fulfilled + 1 pending remainder).')

        # ── Reconciliation ────────────────────────────────────────────
        self.stdout.write('Recording reconciliation data...')
        recon_count = 0
        now = timezone.now()
        for sku, branch_name, sold_qty, delivery_qty, days_ago, resolution, note in RECONCILIATION_DATA:
            prod       = products[sku]
            branch     = branches[branch_name]
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
