from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import date, timedelta
import random

from inventory.models import Product, InventoryMovement, RetailerSales, UserProfile, AuditLog, Branch


def log(user, action, obj, changes=''):
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

PRODUCTS_DATA = [
    ('Kangkong',      'VEG-001', 'Leafy Vegetables'),
    ('Pechay',        'VEG-002', 'Leafy Vegetables'),
    ('Sitaw',         'VEG-003', 'Pod Vegetables'),
    ('Ampalaya',      'VEG-004', 'Gourd Vegetables'),
    ('Kamote Tops',   'VEG-005', 'Leafy Vegetables'),
    ('Malunggay',     'VEG-006', 'Leafy Vegetables'),
    ('Okra',          'VEG-007', 'Pod Vegetables'),
    ('Talong',        'VEG-008', 'Fruit Vegetables'),
    ('Kalabasa',      'VEG-009', 'Gourd Vegetables'),
    ('Kamatis',       'VEG-010', 'Fruit Vegetables'),
    ('Sibuyas Dahon', 'VEG-011', 'Leafy Vegetables'),
    ('Labanos',       'VEG-012', 'Root Vegetables'),
]


class Command(BaseCommand):
    help = 'Seed the database with realistic EFP sample data'

    def handle(self, *args, **options):
        self.stdout.write('Seeding data...')

        # ── Branches ──────────────────────────────────────────────────
        branches = {}
        for name, address in BRANCH_DATA:
            branch, created = Branch.objects.get_or_create(
                name=name,
                defaults={'address': address}
            )
            branches[name] = branch
            if created:
                self.stdout.write(f'  Created branch: {name}')
        branch_list = list(branches.values())

        # ── Users ─────────────────────────────────────────────────────
        users = {}
        role_defs = [
            ('warehouse_staff', 'warehouse', 'Maria',  'Santos'),
            ('sales_rep',       'sales',     'Jose',   'Reyes'),
            ('accountant',      'accountant','Ana',    'Cruz'),
            ('admin_user',      'admin',     'Pedro',  'Dela Cruz'),
        ]
        superuser = User.objects.filter(is_superuser=True).first()

        for username, role, first, last in role_defs:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={'first_name': first, 'last_name': last, 'email': f'{username}@efp.local'}
            )
            if created:
                user.set_password('efp2025')
                user.save()
            UserProfile.objects.update_or_create(user=user, defaults={'role': role})
            users[role] = user
            if created:
                log(superuser, 'create', user, f"role={role}")
                self.stdout.write(f'  Created user: {username} ({role}) — password: efp2025')

        warehouse = users['warehouse']
        sales     = users['sales']
        today     = timezone.now().date()

        # ── Products ──────────────────────────────────────────────────
        products = []
        for name, sku, category in PRODUCTS_DATA:
            prod, created = Product.objects.get_or_create(
                sku=sku,
                defaults={
                    'name': name,
                    'category': category,
                    'quantity': 0,
                    'batch_number': f'BATCH-{sku}-{today.strftime("%Y%m")}',
                    'production_date': today - timedelta(days=random.randint(1, 3)),
                    'expiration_date': today + timedelta(days=random.randint(3, 14)),
                    'unit_price': round(random.uniform(25, 120), 2),
                }
            )
            if created:
                log(warehouse, 'create', prod, f"SKU={prod.sku}, qty={prod.quantity}")
            products.append(prod)
        self.stdout.write(f'  Created {len(products)} products')

        # ── Production In movements ───────────────────────────────────
        for prod in products:
            qty = random.randint(80, 200)
            mv, created = InventoryMovement.objects.get_or_create(
                product=prod,
                movement_type='production_in',
                reference_no=f'PROD-{prod.sku}-01',
                defaults={
                    'quantity': qty,
                    'note': 'Initial harvest batch',
                    'created_by': warehouse,
                }
            )
            if created:
                log(warehouse, 'create', mv, f"type=production_in, qty={qty}, product={prod}")

        # ── Delivery Out movements ────────────────────────────────────
        delivery_count = 0
        for prod in products:
            for branch in random.sample(branch_list, k=random.randint(3, 6)):
                qty = random.randint(10, 35)
                ref = f'DEL-{prod.sku}-{branch.name[:3].upper()}'
                mv, created = InventoryMovement.objects.get_or_create(
                    product=prod,
                    movement_type='delivery_out',
                    reference_no=ref,
                    defaults={
                        'quantity': qty,
                        'destination_branch': branch,
                        'note': f'Weekly delivery to {branch.name}',
                        'created_by': sales,
                    }
                )
                if created:
                    log(sales, 'create', mv,
                        f"type=delivery_out, qty={qty}, product={prod}, branch={branch.name}")
                    delivery_count += 1
        self.stdout.write(f'  Created {delivery_count} delivery movements')

        # ── Loss movements ────────────────────────────────────────────
        for prod in random.sample(products, k=5):
            qty = random.randint(2, 10)
            mv, created = InventoryMovement.objects.get_or_create(
                product=prod,
                movement_type='loss',
                reference_no=f'LOSS-{prod.sku}-01',
                defaults={
                    'quantity': qty,
                    'note': 'Spoilage during transit',
                    'created_by': warehouse,
                }
            )
            if created:
                log(warehouse, 'create', mv, f"type=loss, qty={qty}, product={prod}")

        # ── Return In movements ───────────────────────────────────────
        for prod in random.sample(products, k=3):
            qty    = random.randint(3, 8)
            branch = random.choice(branch_list)
            mv, created = InventoryMovement.objects.get_or_create(
                product=prod,
                movement_type='return_in',
                reference_no=f'RET-{prod.sku}-01',
                defaults={
                    'quantity': qty,
                    'destination_branch': branch,
                    'note': f'Unsold stock returned from {branch.name}',
                    'created_by': sales,
                }
            )
            if created:
                log(sales, 'create', mv,
                    f"type=return_in, qty={qty}, product={prod}, branch={branch.name}")

        # ── Back Orders ───────────────────────────────────────────────
        for prod in random.sample(products, k=2):
            branch = random.choice(branch_list)
            mv, created = InventoryMovement.objects.get_or_create(
                product=prod,
                movement_type='back_order',
                reference_no=f'BO-{prod.sku}-01',
                defaults={
                    'quantity': random.randint(10, 25),
                    'destination_branch': branch,
                    'note': f'Insufficient stock for {branch.name} order',
                    'created_by': sales,
                }
            )
            if created:
                log(sales, 'create', mv,
                    f"type=back_order, product={prod}, branch={branch.name}")

        # ── Retailer Sales (Reconciliation) ───────────────────────────
        recon_count = 0
        for prod in random.sample(products, k=8):
            for branch in random.sample(branch_list, k=random.randint(2, 4)):
                delivery_qty = random.randint(15, 35)
                variance     = random.choice([-3, -2, -1, 0, 0, 0, 1, 2])
                sold_qty     = max(0, delivery_qty + variance)
                rec, created = RetailerSales.objects.get_or_create(
                    product=prod,
                    branch=branch,
                    sales_date=today - timedelta(days=random.randint(0, 7)),
                    defaults={
                        'sold_quantity': sold_qty,
                        'internal_delivery_qty': delivery_qty,
                    }
                )
                if created:
                    log(users['accountant'], 'create', rec,
                        f"branch={branch.name}, product={prod}, sold={sold_qty}, "
                        f"delivery={delivery_qty}, discrepancy={rec.discrepancy}")
                    recon_count += 1
        self.stdout.write(f'  Created {recon_count} reconciliation records')

        self.stdout.write(self.style.SUCCESS('\nDone. Login credentials:'))
        self.stdout.write('  warehouse_staff / efp2025')
        self.stdout.write('  sales_rep       / efp2025')
        self.stdout.write('  accountant      / efp2025')
        self.stdout.write('  admin_user      / efp2025')
