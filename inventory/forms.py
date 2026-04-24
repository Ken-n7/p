from django import forms
from .models import Product, InventoryMovement, RetailerSales

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'sku', 'category', 'quantity', 'batch_number', 
                 'production_date', 'expiration_date', 'unit_price']
        widgets = {
            'production_date': forms.DateInput(attrs={'type': 'date'}),
            'expiration_date': forms.DateInput(attrs={'type': 'date'}),
        }


class InventoryMovementForm(forms.ModelForm):
    class Meta:
        model = InventoryMovement
        fields = ['product', 'movement_type', 'quantity', 'destination_branch', 
                 'reference_no', 'note']
        widgets = {
            'note': forms.Textarea(attrs={'rows': 3}),
        }


class RetailerSalesForm(forms.ModelForm):
    class Meta:
        model = RetailerSales
        fields = ['product', 'branch', 'sold_quantity', 'sales_date', 
                 'internal_delivery_qty']
        widgets = {
            'sales_date': forms.DateInput(attrs={'type': 'date'}),
        }