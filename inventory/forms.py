from django import forms
from django.utils import timezone
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import Product, InventoryMovement, RetailerSales, UserProfile, Branch

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'sku', 'category', 'quantity', 'batch_number',
                 'production_date', 'expiration_date', 'unit_price']
        widgets = {
            'production_date': forms.DateInput(attrs={'type': 'date'}),
            'expiration_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        production_date = cleaned_data.get('production_date')
        expiration_date = cleaned_data.get('expiration_date')
        if production_date and expiration_date and expiration_date <= production_date:
            raise forms.ValidationError("Expiration date must be after the production date.")
        unit_price = cleaned_data.get('unit_price')
        if unit_price is not None and unit_price <= 0:
            self.add_error('unit_price', "Unit price must be greater than zero.")
        return cleaned_data


class InventoryMovementForm(forms.ModelForm):
    class Meta:
        model = InventoryMovement
        fields = ['product', 'movement_type', 'quantity', 'destination_branch',
                 'reference_no', 'note']
        widgets = {
            'note': forms.Textarea(attrs={'rows': 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        quantity = cleaned_data.get('quantity')
        movement_type = cleaned_data.get('movement_type')
        product = cleaned_data.get('product')
        destination_branch = cleaned_data.get('destination_branch')

        if quantity is not None and quantity == 0:
            self.add_error('quantity', "Quantity must be greater than zero.")

        BRANCH_REQUIRED = {'delivery_out', 'back_order'}
        if movement_type in BRANCH_REQUIRED and not destination_branch:
            self.add_error('destination_branch', "A destination branch is required for this movement type.")

        if movement_type == 'delivery_out' and product and quantity:
            if quantity > product.quantity:
                self.add_error('quantity',
                    f"Cannot deliver {quantity} units — only {product.quantity} in stock.")

        return cleaned_data


class RetailerSalesForm(forms.ModelForm):
    branch = forms.ModelChoiceField(
        queryset=Branch.objects.all(),
        empty_label="Select a branch",
    )

    class Meta:
        model = RetailerSales
        fields = ['product', 'branch', 'sold_quantity', 'sales_date',
                  'internal_delivery_qty']
        widgets = {
            'sales_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        sold = cleaned_data.get('sold_quantity')
        delivered = cleaned_data.get('internal_delivery_qty')
        sales_date = cleaned_data.get('sales_date')

        if sold is not None and delivered is not None and sold > delivered:
            raise forms.ValidationError(
                f"Sold quantity ({sold}) cannot exceed internal delivery quantity ({delivered})."
            )
        if sales_date and sales_date > timezone.now().date():
            self.add_error('sales_date', "Sales date cannot be in the future.")

        return cleaned_data


class BranchForm(forms.ModelForm):
    class Meta:
        model = Branch
        fields = ['name', 'address']


class UserCreateForm(UserCreationForm):
    role = forms.ChoiceField(choices=UserProfile.ROLE_CHOICES)

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password1', 'password2', 'role']

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            UserProfile.objects.update_or_create(user=user, defaults={'role': self.cleaned_data['role']})
        return user


class UserEditForm(forms.ModelForm):
    role = forms.ChoiceField(choices=UserProfile.ROLE_CHOICES)

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'role']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and hasattr(self.instance, 'profile'):
            self.fields['role'].initial = self.instance.profile.role

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            UserProfile.objects.update_or_create(user=user, defaults={'role': self.cleaned_data['role']})
        return user