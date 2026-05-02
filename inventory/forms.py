from django import forms
from django.db.models import Sum
from django.utils import timezone
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import Product, InventoryMovement, RetailerSales, UserProfile, Branch

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'sku', 'category', 'unit', 'unit_price']

    def clean(self):
        cleaned_data = super().clean()
        unit_price = cleaned_data.get('unit_price')
        if unit_price is not None and unit_price <= 0:
            self.add_error('unit_price', "Unit price must be greater than zero.")
        return cleaned_data


class InventoryMovementForm(forms.ModelForm):
    confirm_override = forms.BooleanField(
        required=False,
        label="I acknowledge the warning above and confirm this entry is correct",
    )

    class Meta:
        model = InventoryMovement
        fields = ['product', 'movement_type', 'quantity', 'source_batch', 'destination_branch',
                 'reference_no', 'batch_number', 'production_date', 'expiration_date', 'note']
        widgets = {
            'production_date': forms.DateInput(attrs={'type': 'date'}),
            'expiration_date': forms.DateInput(attrs={'type': 'date'}),
            'note': forms.Textarea(attrs={'rows': 3}),
        }

    WAREHOUSE_TYPES = {'production_in', 'return_in', 'loss'}
    SALES_TYPES     = {'delivery_out', 'back_order'}

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if not self._can_override():
            del self.fields['confirm_override']
        allowed = self._allowed_types()
        if allowed is not None:
            self.fields['movement_type'].choices = [
                c for c in self.fields['movement_type'].choices if c[0] in allowed
            ]
        self.fields['batch_number'].required = False
        self.fields['production_date'].required = False
        self.fields['expiration_date'].required = False
        self.fields['source_batch'].required = False
        self.fields['source_batch'].queryset = InventoryMovement.objects.filter(
            movement_type='production_in'
        ).order_by('product__name', 'expiration_date')
        self.fields['source_batch'].label = 'Batch'
        self.fields['source_batch'].empty_label = 'Select a batch'

    def _can_override(self):
        if not self.user:
            return False
        if self.user.is_superuser:
            return True
        profile = getattr(self.user, 'profile', None)
        return profile and profile.role in ('admin', 'accountant')

    def _allowed_types(self):
        if not self.user:
            return None
        if self.user.is_superuser:
            return None
        profile = getattr(self.user, 'profile', None)
        if not profile:
            return None
        if profile.role == 'warehouse':
            return self.WAREHOUSE_TYPES
        if profile.role == 'sales':
            return self.SALES_TYPES
        return None

    def clean(self):
        cleaned_data = super().clean()
        quantity      = cleaned_data.get('quantity')
        movement_type = cleaned_data.get('movement_type')
        product       = cleaned_data.get('product')
        branch        = cleaned_data.get('destination_branch')
        reference_no  = cleaned_data.get('reference_no', '').strip()
        can_override  = self._can_override()
        confirmed     = cleaned_data.get('confirm_override', False)
        source_batch  = cleaned_data.get('source_batch')

        allowed = self._allowed_types()
        if allowed is not None and movement_type and movement_type not in allowed:
            self.add_error('movement_type', "You are not permitted to record this movement type.")

        if quantity is not None and quantity == 0:
            self.add_error('quantity', "Quantity must be greater than zero.")

        BRANCH_REQUIRED = {'delivery_out', 'back_order', 'return_in'}
        if movement_type in BRANCH_REQUIRED and not branch:
            self.add_error('destination_branch', "A destination branch is required for this movement type.")

        REF_REQUIRED = {'delivery_out', 'return_in'}
        if movement_type in REF_REQUIRED and not reference_no:
            self.add_error('reference_no', "A reference number is required for deliveries and returns.")

        if movement_type == 'delivery_out' and product and quantity:
            if source_batch:
                pass
            elif quantity > product.quantity:
                self.add_error('quantity',
                    f"Cannot deliver {quantity} {product.unit} — only {product.quantity} in stock.")

        # Rule 5: loss cannot exceed current stock
        if movement_type == 'loss' and product and quantity:
            if source_batch:
                pass
            elif quantity > product.quantity:
                self.add_error('quantity',
                    f"Cannot record a loss of {quantity} {product.unit} — only {product.quantity} in stock.")


        BATCH_REQUIRED = {'delivery_out', 'loss'}
        if movement_type in BATCH_REQUIRED:
            if not source_batch:
                self.add_error('source_batch', 'A batch must be selected for this movement type.')
            elif product and source_batch.product != product:
                self.add_error('source_batch', 'Selected batch does not belong to the chosen product.')
            elif quantity and source_batch:
                avail = source_batch.available_quantity()
                if quantity > avail:
                    self.add_error('quantity',
                        f"Cannot use {quantity} {product.unit} from this batch — only {avail} available.")

        if movement_type == 'return_in' and source_batch and product:
            if source_batch.product != product:
                self.add_error('source_batch', 'Selected batch does not belong to the chosen product.')

        # Rules 1 & 2: return_in sequence checks (only when branch is present)
        if movement_type == 'return_in' and product and branch:
            total_delivered = InventoryMovement.objects.filter(
                product=product, movement_type='delivery_out', destination_branch=branch,
            ).aggregate(total=Sum('quantity'))['total'] or 0

            if total_delivered == 0:
                # Rule 1: no prior delivery to this branch for this product
                msg = f"No delivery has been recorded for {product.name} at {branch}."
                if can_override and not confirmed:
                    self.add_error('confirm_override',
                        f"Warning: {msg} Check the box below to proceed anyway.")
                elif not can_override:
                    self.add_error('destination_branch', msg)
            elif quantity:
                # Rule 2: return qty cannot exceed net delivered
                total_returned = InventoryMovement.objects.filter(
                    product=product, movement_type='return_in', destination_branch=branch,
                ).aggregate(total=Sum('quantity'))['total'] or 0
                net = total_delivered - total_returned
                if quantity > net:
                    self.add_error('quantity',
                        f"Cannot return {quantity} units — net delivered to {branch} is {net} units.")

        # Rule 3: back_order when stock is actually sufficient
        if movement_type == 'back_order' and product and quantity:
            if product.quantity >= quantity:
                msg = (f"Current stock ({product.quantity} units) is sufficient to fulfill this order. "
                       f"A back order may not be needed.")
                if can_override and not confirmed:
                    self.add_error('confirm_override',
                        f"Warning: {msg} Check the box below to proceed anyway.")
                elif not can_override:
                    self.add_error('movement_type', msg)

        if movement_type == 'production_in':
            batch_number = cleaned_data.get('batch_number')
            production_date = cleaned_data.get('production_date')
            expiration_date = cleaned_data.get('expiration_date')
            if not batch_number:
                self.add_error('batch_number', "Batch number is required for production entries.")
            if not production_date:
                self.add_error('production_date', "Production date is required for production entries.")
            if not expiration_date:
                self.add_error('expiration_date', "Expiration date is required for production entries.")
            if production_date and expiration_date and expiration_date <= production_date:
                self.add_error('expiration_date', "Expiration date must be after the production date.")

        return cleaned_data


class RetailerSalesForm(forms.ModelForm):
    delivery_movement = forms.ModelChoiceField(
        queryset=InventoryMovement.objects.filter(
            movement_type='delivery_out'
        ).select_related('product', 'destination_branch').order_by('-created_at'),
        required=False,
        empty_label='— Select a delivery to auto-fill (optional) —',
        label='Link to Delivery',
    )
    branch = forms.ModelChoiceField(
        queryset=Branch.objects.all(),
        empty_label='Select a branch',
    )

    class Meta:
        model = RetailerSales
        fields = ['delivery_movement', 'product', 'branch', 'sold_quantity',
                  'sales_date', 'internal_delivery_qty']
        widgets = {
            'sales_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        dm = cleaned_data.get('delivery_movement')

        if dm:
            cleaned_data['product'] = dm.product
            cleaned_data['branch'] = dm.destination_branch
            cleaned_data['internal_delivery_qty'] = dm.quantity

        sold = cleaned_data.get('sold_quantity')
        delivered = cleaned_data.get('internal_delivery_qty')
        sales_date = cleaned_data.get('sales_date')

        if sold is not None and delivered is not None and sold > delivered:
            raise forms.ValidationError(
                f"Sold quantity ({sold}) cannot exceed internal delivery quantity ({delivered})."
            )
        if sales_date and sales_date > timezone.now().date():
            self.add_error('sales_date', 'Sales date cannot be in the future.')

        return cleaned_data


class ReconciliationResolveForm(forms.Form):
    resolution_status = forms.ChoiceField(
        choices=[
            ('returned',    'Returned to Warehouse — goods were physically sent back'),
            ('written_off', 'Written Off — expired or damaged at branch'),
            ('corrected',   'Corrected Entry — counting or recording error'),
        ],
        label='Resolution Type',
    )
    resolution_note = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        label='Resolution Note',
        help_text='Briefly describe how this discrepancy was resolved.',
    )


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


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')


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
