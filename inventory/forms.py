from django import forms
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


class _MovementFormMixin:
    def _can_override(self):
        user = getattr(self, 'user', None)
        if not user:
            return False
        if user.is_superuser:
            return True
        profile = getattr(user, 'profile', None)
        return profile and profile.role in ('admin', 'accountant')

    def _style(self):
        for field in self.fields.values():
            widget = field.widget
            if not isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault('class', 'form-control')


class ProductionInForm(_MovementFormMixin, forms.ModelForm):
    class Meta:
        model = InventoryMovement
        fields = ['product', 'quantity', 'batch_number', 'production_date', 'expiration_date', 'note']
        widgets = {
            'production_date': forms.DateInput(attrs={'type': 'date'}),
            'expiration_date': forms.DateInput(attrs={'type': 'date'}),
            'note': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self._style()

    def clean(self):
        cleaned_data = super().clean()
        batch_number = cleaned_data.get('batch_number')
        production_date = cleaned_data.get('production_date')
        expiration_date = cleaned_data.get('expiration_date')
        quantity = cleaned_data.get('quantity')

        if not batch_number:
            self.add_error('batch_number', 'Batch number is required.')
        if not production_date:
            self.add_error('production_date', 'Production date is required.')
        if not expiration_date:
            self.add_error('expiration_date', 'Expiration date is required.')
        if production_date and expiration_date and expiration_date <= production_date:
            self.add_error('expiration_date', 'Expiration date must be after the production date.')
        if quantity is not None and quantity == 0:
            self.add_error('quantity', 'Quantity must be greater than zero.')
        return cleaned_data


class DeliveryOutForm(_MovementFormMixin, forms.ModelForm):
    source_batch = forms.ModelChoiceField(
        queryset=InventoryMovement.objects.filter(movement_type='production_in').order_by('product__name', 'expiration_date'),
        required=True,
        empty_label='Select a batch',
        label='Batch',
    )
    destination_branch = forms.ModelChoiceField(
        queryset=Branch.objects.all(),
        empty_label='Select a branch',
        label='Branch',
    )
    closes_back_order = forms.ModelChoiceField(
        queryset=InventoryMovement.objects.filter(movement_type='back_order', back_order_status='pending').order_by('product__name'),
        required=False,
        empty_label='— None (does not close a back order) —',
        label='Closes Back Order',
    )

    class Meta:
        model = InventoryMovement
        fields = ['closes_back_order', 'product', 'source_batch', 'destination_branch', 'quantity', 'reference_no', 'note']
        widgets = {
            'note': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self._style()

    def clean(self):
        cleaned_data = super().clean()
        product = cleaned_data.get('product')
        source_batch = cleaned_data.get('source_batch')
        branch = cleaned_data.get('destination_branch')
        quantity = cleaned_data.get('quantity')
        ref = cleaned_data.get('reference_no', '').strip()
        closes_bo = cleaned_data.get('closes_back_order')

        if not branch:
            self.add_error('destination_branch', 'A branch is required for delivery.')
        if not ref:
            self.add_error('reference_no', 'A reference number is required for deliveries.')
        if not source_batch:
            self.add_error('source_batch', 'A batch must be selected.')
        if quantity is not None and quantity == 0:
            self.add_error('quantity', 'Quantity must be greater than zero.')
        if source_batch and product and source_batch.product != product:
            self.add_error('source_batch', 'Selected batch does not belong to the chosen product.')
        if source_batch and quantity:
            avail = source_batch.available_quantity()
            if quantity > avail:
                self.add_error('quantity', f"Only {avail} {product.unit if product else 'units'} available in this batch.")
        if closes_bo and product and closes_bo.product != product:
            self.add_error('closes_back_order', 'Selected back order is for a different product.')
        if closes_bo and branch and closes_bo.destination_branch != branch:
            self.add_error('closes_back_order', 'Selected back order is for a different branch.')
        return cleaned_data


class ReturnInForm(_MovementFormMixin, forms.ModelForm):
    destination_branch = forms.ModelChoiceField(
        queryset=Branch.objects.all(),
        empty_label='Select a branch',
        label='Branch',
    )
    source_delivery = forms.ModelChoiceField(
        queryset=InventoryMovement.objects.filter(movement_type='delivery_out').order_by('-created_at'),
        required=True,
        empty_label='Select the original delivery',
        label='Original Delivery',
    )

    class Meta:
        model = InventoryMovement
        fields = ['source_delivery', 'product', 'destination_branch', 'quantity', 'reference_no', 'note']
        widgets = {
            'note': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self._style()

    def clean(self):
        cleaned_data = super().clean()
        product = cleaned_data.get('product')
        branch = cleaned_data.get('destination_branch')
        source_delivery = cleaned_data.get('source_delivery')
        quantity = cleaned_data.get('quantity')
        ref = cleaned_data.get('reference_no', '').strip()

        if not branch:
            self.add_error('destination_branch', 'A branch is required.')
        if not ref:
            self.add_error('reference_no', 'A reference number is required for returns.')
        if not source_delivery:
            self.add_error('source_delivery', 'The original delivery must be selected.')
        if quantity is not None and quantity == 0:
            self.add_error('quantity', 'Quantity must be greater than zero.')
        if source_delivery and product and source_delivery.product != product:
            self.add_error('source_delivery', 'Selected delivery is for a different product.')
        if source_delivery and branch and source_delivery.destination_branch != branch:
            self.add_error('source_delivery', 'Selected delivery did not go to this branch.')
        if source_delivery and quantity:
            from django.db.models import Sum
            already_returned = InventoryMovement.objects.filter(
                source_delivery=source_delivery,
                movement_type='return_in',
            ).aggregate(total=Sum('quantity'))['total'] or 0
            returnable = source_delivery.quantity - already_returned
            if quantity > returnable:
                self.add_error('quantity', f"Cannot return {quantity} — only {returnable} returnable from this delivery.")
        return cleaned_data


class LossForm(_MovementFormMixin, forms.ModelForm):
    source_batch = forms.ModelChoiceField(
        queryset=InventoryMovement.objects.filter(movement_type='production_in').order_by('product__name', 'expiration_date'),
        required=True,
        empty_label='Select a batch',
        label='Batch',
    )
    source_delivery = forms.ModelChoiceField(
        queryset=InventoryMovement.objects.filter(movement_type='delivery_out').order_by('-created_at'),
        required=False,
        empty_label='— Warehouse loss (no delivery) —',
        label='Related Delivery (if transit or branch loss)',
    )

    class Meta:
        model = InventoryMovement
        fields = ['loss_location', 'source_delivery', 'product', 'source_batch', 'quantity', 'note']
        widgets = {
            'note': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self._style()
        self.fields['loss_location'].required = True

    def clean(self):
        cleaned_data = super().clean()
        product = cleaned_data.get('product')
        source_batch = cleaned_data.get('source_batch')
        source_delivery = cleaned_data.get('source_delivery')
        loss_location = cleaned_data.get('loss_location')
        quantity = cleaned_data.get('quantity')

        if not loss_location:
            self.add_error('loss_location', 'Loss location is required.')
        if not source_batch:
            self.add_error('source_batch', 'A batch must be selected.')
        if quantity is not None and quantity == 0:
            self.add_error('quantity', 'Quantity must be greater than zero.')
        if source_batch and product and source_batch.product != product:
            self.add_error('source_batch', 'Selected batch does not belong to the chosen product.')
        if source_batch and quantity:
            avail = source_batch.available_quantity()
            if quantity > avail:
                self.add_error('quantity', f"Only {avail} {product.unit if product else 'units'} available in this batch.")
        if loss_location == 'transit' and not source_delivery:
            self.add_error('source_delivery', 'A related delivery is required for transit losses.')
        if source_delivery and product and source_delivery.product != product:
            self.add_error('source_delivery', 'Selected delivery is for a different product.')
        return cleaned_data


class BackOrderForm(_MovementFormMixin, forms.ModelForm):
    destination_branch = forms.ModelChoiceField(
        queryset=Branch.objects.all(),
        empty_label='Select a branch',
        label='Branch',
    )

    class Meta:
        model = InventoryMovement
        fields = ['product', 'destination_branch', 'quantity', 'note']
        widgets = {
            'note': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self._style()

    def clean(self):
        cleaned_data = super().clean()
        branch = cleaned_data.get('destination_branch')
        quantity = cleaned_data.get('quantity')

        if not branch:
            self.add_error('destination_branch', 'A branch is required.')
        if quantity is not None and quantity == 0:
            self.add_error('quantity', 'Quantity must be greater than zero.')
        return cleaned_data


class RetailerSalesForm(forms.ModelForm):
    delivery_movement = forms.ModelChoiceField(
        queryset=InventoryMovement.objects.filter(
            movement_type='delivery_out'
        ).exclude(
            reconciliations__isnull=False
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
        labels = {
            'internal_delivery_qty': 'Quantity We Delivered',
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

# rest unchanged
class ReconciliationResolveForm(forms.Form):
    POSITIVE_CHOICES = [
        ('returned',    'Returned to Warehouse — goods were physically sent back'),
        ('written_off', 'Written Off — expired or damaged at branch'),
        ('corrected',   'Corrected Entry — counting or recording error'),
    ]
    NEGATIVE_CHOICES = [
        ('over_sold',  'Sales Exceeded Delivery — branch sold more than EFP delivered'),
        ('corrected',  'Corrected Entry — counting or recording error'),
    ]

    resolution_status = forms.ChoiceField(choices=POSITIVE_CHOICES, label='Resolution Type')
    resolution_note = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        label='Resolution Note',
        help_text='Briefly describe how this discrepancy was resolved.',
    )

    def __init__(self, *args, discrepancy=0, **kwargs):
        super().__init__(*args, **kwargs)
        if discrepancy < 0:
            self.fields['resolution_status'].choices = self.NEGATIVE_CHOICES
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')

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
        if commit: UserProfile.objects.update_or_create(user=user, defaults={'role': self.cleaned_data['role']})
        return user
class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values(): field.widget.attrs.setdefault('class', 'form-control')
class UserEditForm(forms.ModelForm):
    role = forms.ChoiceField(choices=UserProfile.ROLE_CHOICES)
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'role']
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and hasattr(self.instance, 'profile'): self.fields['role'].initial = self.instance.profile.role
    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit: UserProfile.objects.update_or_create(user=user, defaults={'role': self.cleaned_data['role']})
        return user
