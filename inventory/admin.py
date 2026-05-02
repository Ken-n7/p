from django.contrib import admin
from .models import Product, InventoryMovement, RetailerSales, Branch


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ['name', 'address']
    search_fields = ['name']

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'sku', 'quantity', 'unit_price', 'created_at']
    search_fields = ['name', 'sku']
    list_filter = ['category', 'unit']


@admin.register(InventoryMovement)
class InventoryMovementAdmin(admin.ModelAdmin):
    list_display = ['product', 'get_movement_type_display', 'quantity', 'destination_branch', 'created_at', 'created_by']
    list_filter = ['movement_type', 'destination_branch']
    search_fields = ['product__name', 'reference_no']


@admin.register(RetailerSales)
class RetailerSalesAdmin(admin.ModelAdmin):
    list_display = ['product', 'branch', 'sold_quantity', 'sales_date', 'reconciled']
    list_filter = ['branch', 'reconciled', 'sales_date']