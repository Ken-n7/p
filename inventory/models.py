from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Product(models.Model):
    UNIT_CHOICES = [
        ('kg',     'kg'),
        ('pcs',    'pcs'),
        ('bundle', 'bundle'),
        ('tray',   'tray'),
        ('bag',    'bag'),
    ]

    name = models.CharField(max_length=200)
    sku = models.CharField(max_length=50, unique=True)
    category = models.CharField(max_length=100, default="Fresh Produce")
    quantity = models.PositiveIntegerField(default=0)
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default='pcs')
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.sku})"

    class Meta:
        ordering = ['-created_at']


class Branch(models.Model):
    name = models.CharField(max_length=100, unique=True)
    address = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Branches'


class InventoryMovement(models.Model):
    MOVEMENT_TYPES = [
        ('production_in', 'Production In'),
        ('delivery_out', 'Delivery Out'),
        ('return_in', 'Return In'),
        ('loss', 'Loss'),
        ('back_order', 'Back Order'),
    ]

    # Types that increase stock vs decrease stock
    INBOUND_TYPES = {'production_in', 'return_in'}
    OUTBOUND_TYPES = {'delivery_out', 'loss'}
    # back_order is recorded but does not affect current stock level

    LOSS_LOCATION_CHOICES = [('warehouse', 'Warehouse'), ('transit', 'In Transit'), ('branch', 'At Branch')]
    BACK_ORDER_STATUS_CHOICES = [('pending', 'Pending'), ('fulfilled', 'Fulfilled'), ('cancelled', 'Cancelled')]

    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPES)
    quantity = models.PositiveIntegerField()
    destination_branch = models.ForeignKey('Branch', on_delete=models.SET_NULL, null=True, blank=True, related_name='movements')
    reference_no = models.CharField(max_length=100, blank=True)
    note = models.TextField(blank=True)
    batch_number = models.CharField(max_length=50, blank=True)
    production_date = models.DateField(null=True, blank=True)
    expiration_date = models.DateField(null=True, blank=True)
    source_batch = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deductions',
        limit_choices_to={'movement_type': 'production_in'},
    )
    loss_location = models.CharField(max_length=10, choices=LOSS_LOCATION_CHOICES, null=True, blank=True)
    source_delivery = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='linked_movements', limit_choices_to={'movement_type': 'delivery_out'})
    closes_back_order = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='fulfillment', limit_choices_to={'movement_type': 'back_order'})
    back_order_status = models.CharField(max_length=10, choices=BACK_ORDER_STATUS_CHOICES, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        if is_new:
            product = self.product
            if self.movement_type in self.INBOUND_TYPES:
                product.quantity += self.quantity
            elif self.movement_type in self.OUTBOUND_TYPES:
                product.quantity = max(0, product.quantity - self.quantity)
            product.save(update_fields=['quantity'])
        super().save(*args, **kwargs)

    def available_quantity(self):
        if self.movement_type != 'production_in':
            return None
        from django.db.models import Sum
        deducted = self.deductions.filter(
            movement_type__in=['delivery_out', 'loss']
        ).aggregate(total=Sum('quantity'))['total'] or 0
        returned = self.deductions.filter(
            movement_type='return_in'
        ).aggregate(total=Sum('quantity'))['total'] or 0
        return self.quantity - deducted + returned

    def __str__(self):
        return f"{self.get_movement_type_display()} - {self.product.name} ({self.quantity})"


class RetailerSales(models.Model):
    """For reconciliation with SM / Savemore"""

    RESOLUTION_CHOICES = [
        ('pending',      'Pending'),
        ('returned',     'Returned to Warehouse'),
        ('written_off',  'Written Off'),
        ('corrected',    'Corrected Entry'),
    ]

    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    branch = models.ForeignKey('Branch', on_delete=models.SET_NULL, null=True, blank=True, related_name='sales')
    delivery_movement = models.ForeignKey(
        'InventoryMovement',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reconciliations',
        limit_choices_to={'movement_type': 'delivery_out'},
    )
    sold_quantity = models.PositiveIntegerField()
    sales_date = models.DateField()
    internal_delivery_qty = models.PositiveIntegerField(null=True, blank=True)
    discrepancy = models.IntegerField(null=True, blank=True)
    reconciled = models.BooleanField(default=False)
    resolution_status = models.CharField(max_length=20, choices=RESOLUTION_CHOICES, default='pending')
    resolution_note = models.TextField(blank=True)
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_sales')
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.internal_delivery_qty is not None:
            self.discrepancy = self.internal_delivery_qty - self.sold_quantity
            if self.discrepancy == 0:
                self.reconciled = True
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.branch} - {self.product.name} ({self.sales_date})"


# ================== AUDIT LOG ==================
class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('create', 'Created'),
        ('update', 'Updated'),
        ('delete', 'Deleted'),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=50)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    object_repr = models.CharField(max_length=255)
    changes = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"[{self.timestamp:%Y-%m-%d %H:%M}] {self.user} {self.action} {self.model_name}: {self.object_repr}"


# ================== USER ROLES ==================
class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Admin/Owner'),
        ('warehouse', 'Warehouse Staff'),
        ('sales', 'Sales & Distribution'),
        ('accountant', 'Accountant'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='warehouse')
    
    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"
