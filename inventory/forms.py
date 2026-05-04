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

    class Meta:
        model = InventoryMovement
        fields = ['product', 'source_batch', 'destination_branch', 'quantity', 'reference_no', 'note']
        widgets = {
            'note': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self._style()
        self.fields['source_batch'].label_from_instance = lambda obj: (
            f"{obj.batch_number} — exp {obj.expiration_date}"
            f" ({obj.available_quantity()} {obj.product.unit} available)"
        )

    def clean(self):
        cleaned_data = super().clean()
        product = cleaned_data.get('product')
        source_batch = cleaned_data.get('source_batch')
        branch = cleaned_data.get('destination_branch')
        quantity = cleaned_data.get('quantity')
        ref = cleaned_data.get('reference_no', '').strip()

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
        empty_label='Select a delivery',
        label='Related Delivery',
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
        self.fields['source_delivery'].label_from_instance = lambda obj: (
            f"{obj.reference_no or 'No ref'} — {obj.product.name}"
            f" → {obj.destination_branch or '?'} ({obj.quantity} {obj.product.unit}, {obj.created_at.strftime('%b %d, %Y')})"
        )
        self.fields['source_batch'].label_from_instance = lambda obj: (
            f"{obj.batch_number} — exp {obj.expiration_date}"
            f" ({obj.available_quantity()} {obj.product.unit} available)"
        )

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


class RetailerSalesForm(forms.ModelForm):
    delivery_movement = forms.ModelChoiceField(
        queryset=InventoryMovement.objects.filter(
            movement_type='delivery_out'
        ).exclude(
            reconciliations__isnull=False
        ).select_related('product', 'destination_branch').order_by('-created_at'),
        required=True,
        empty_label='Select a delivery',
        label='Delivery',
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


class ReconciliationResolveForm(forms.Form):
    RESOLUTION_CHOICES = [
        ('written_off', 'Written Off — expired or damaged at branch'),
        ('corrected',   'Corrected Entry — counting or recording error'),
    ]

    resolution_status = forms.ChoiceField(choices=RESOLUTION_CHOICES, label='Resolution Type')
    resolution_note = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        label='Resolution Note',
        help_text='Briefly describe how this discrepancy was resolved.',
    )
    corrected_sold_quantity = forms.IntegerField(
        required=False,
        min_value=1,
        label='Corrected Sold Quantity',
        help_text='Enter the actual correct quantity sold. A new reconciliation record will be created with this value.',
    )

    def __init__(self, *args, internal_delivery_qty=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.internal_delivery_qty = internal_delivery_qty
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')

    def clean(self):
        cleaned_data = super().clean()
        resolution_status = cleaned_data.get('resolution_status')
        corrected_qty = cleaned_data.get('corrected_sold_quantity')

        if resolution_status == 'corrected':
            if corrected_qty is None:
                self.add_error('corrected_sold_quantity', 'Corrected sold quantity is required when selecting Corrected Entry.')
            elif self.internal_delivery_qty and corrected_qty > self.internal_delivery_qty:
                self.add_error(
                    'corrected_sold_quantity',
                    f'Corrected quantity cannot exceed the delivered quantity ({self.internal_delivery_qty}).',
                )

        return cleaned_data

def _save_user_profile(user, role):
    UserProfile.objects.update_or_create(user=user, defaults={'role': role})


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
            _save_user_profile(user, self.cleaned_data['role'])
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
            _save_user_profile(user, self.cleaned_data['role'])
        return user
