from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Product(models.Model):
    name = models.CharField(max_length=200)
    sku = models.CharField(max_length=50, unique=True)
    category = models.CharField(max_length=100, default="Fresh Produce")
    quantity = models.PositiveIntegerField(default=0)
    batch_number = models.CharField(max_length=50, blank=True)
    production_date = models.DateField(null=True, blank=True)
    expiration_date = models.DateField(null=True, blank=True)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.sku})"

    class Meta:
        ordering = ['-created_at']


class InventoryMovement(models.Model):
    MOVEMENT_TYPES = [
        ('production_in', 'Production In'),
        ('delivery_out', 'Delivery Out'),
        ('return_in', 'Return In'),
        ('loss', 'Loss'),
        ('back_order', 'Back Order'),
    ]

    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPES)
    quantity = models.PositiveIntegerField()
    destination_branch = models.CharField(max_length=100, blank=True)
    reference_no = models.CharField(max_length=100, blank=True)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.get_movement_type_display()} - {self.product.name} ({self.quantity})"


class RetailerSales(models.Model):
    """For reconciliation with SM / Savemore"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    branch = models.CharField(max_length=100)
    sold_quantity = models.PositiveIntegerField()
    sales_date = models.DateField()
    internal_delivery_qty = models.PositiveIntegerField(null=True, blank=True)
    discrepancy = models.IntegerField(null=True, blank=True)
    reconciled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def save(self, *args, **kwargs):
        if self.internal_delivery_qty is not None:
            self.discrepancy = self.internal_delivery_qty - self.sold_quantity
            if self.discrepancy == 0:
                self.reconciled = True
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.branch} - {self.product.name} ({self.sales_date})"


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