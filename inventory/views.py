from functools import wraps

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Sum, Count, Exists, OuterRef
from django.forms import ModelChoiceField

from .models import Product, InventoryMovement, RetailerSales, AuditLog, Branch
from .forms import (
    ProductForm, RetailerSalesForm, BranchForm, ReconciliationResolveForm,
    ProductionInForm, DeliveryOutForm, LossForm, BackOrderForm,
    UserCreateForm, UserEditForm, ProfileForm,
)


_TYPE_ROLES = {
    'production_in': ('admin', 'warehouse'),
    'delivery_out':  ('admin', 'sales'),
    'loss':          ('admin', 'warehouse'),
    'back_order':    ('admin', 'sales'),
}

_MOVEMENT_FORMS = {
    'production_in': ProductionInForm,
    'delivery_out':  DeliveryOutForm,
    'loss':          LossForm,
    'back_order':    BackOrderForm,
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def _has_role(user, *roles):
    if user.is_superuser:
        return True
    profile = getattr(user, 'profile', None)
    return profile and profile.role in roles


def require_role(*roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not _has_role(request.user, *roles):
                messages.error(request, 'Access denied.')
                return redirect('dashboard')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def _log(user, action, obj, changes=''):
    AuditLog.objects.create(
        user=user if user.is_authenticated else None,
        action=action,
        model_name=obj.__class__.__name__,
        object_id=obj.pk,
        object_repr=str(obj),
        changes=changes,
    )


def _handle_back_order_fulfillment(movement, user):
    """Mark back order fulfilled; create remainder BO if partial. Returns remainder qty or None."""
    bo = movement.closes_back_order
    bo.back_order_status = 'fulfilled'
    bo.save(update_fields=['back_order_status'])
    if movement.quantity >= bo.quantity:
        return None
    remainder = bo.quantity - movement.quantity
    new_bo = InventoryMovement(
        product=bo.product,
        movement_type='back_order',
        quantity=remainder,
        destination_branch=bo.destination_branch,
        back_order_status='pending',
        note=f"Remainder from partial fulfillment of back order #{bo.pk} — originally {bo.quantity} {bo.product.unit}, delivered {movement.quantity}",
        created_by=user,
    )
    new_bo.save()
    _log(user, 'create', new_bo, f"type=back_order, qty={new_bo.quantity}, product={new_bo.product}")
    return remainder


def _diff(form):
    """Return a readable string of changed fields for an edit form."""
    if not form.changed_data:
        return ''
    parts = []
    for field in form.changed_data:
        old = form.initial.get(field, '—')
        new = form.cleaned_data.get(field, '—')
        field_obj = form.fields.get(field)
        if isinstance(field_obj, ModelChoiceField) and old not in ('—', None, ''):
            try:
                old = field_obj.queryset.get(pk=old)
            except Exception:
                pass
        parts.append(f"{field}: '{old}' → '{new}'")
    return ' | '.join(parts)


# ── Dashboard ─────────────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    profile = getattr(request.user, 'profile', None)
    role = profile.role if profile else ('admin' if request.user.is_superuser else 'warehouse')

    total_products = Product.objects.count()
    total_movements = InventoryMovement.objects.count()
    low_stock = Product.objects.filter(quantity__lt=10)
    near_expiry = InventoryMovement.objects.filter(
        movement_type='production_in',
        expiration_date__isnull=False,
        expiration_date__lte=timezone.now().date() + timezone.timedelta(days=7)
    ).select_related('product').order_by('expiration_date')
    recent_movements = InventoryMovement.objects.select_related('product', 'created_by', 'destination_branch').order_by('-created_at')[:10]
    deliveries_by_branch = (
        InventoryMovement.objects
        .filter(movement_type='delivery_out')
        .values('destination_branch__name')
        .annotate(total_qty=Sum('quantity'))
        .order_by('-total_qty')
    )

    can_see_recon = _has_role(request.user, 'admin', 'accountant')
    pending_recon_count = 0
    pending_discrepancy = 0
    if can_see_recon:
        pending = RetailerSales.objects.filter(reconciled=False)
        pending_recon_count = pending.count()
        pending_discrepancy = pending.aggregate(total=Sum('discrepancy'))['total'] or 0

    context = {
        'total_products': total_products,
        'total_movements': total_movements,
        'low_stock_count': low_stock.count(),
        'low_stock': low_stock[:5],
        'near_expiry_count': near_expiry.count(),
        'near_expiry': near_expiry[:5],
        'recent_movements': recent_movements,
        'deliveries_by_branch': deliveries_by_branch,
        'user_role': role,
        'can_see_recon': can_see_recon,
        'pending_recon_count': pending_recon_count,
        'pending_discrepancy': pending_discrepancy,
        'title': 'Dashboard',
    }
    return render(request, 'inventory/dashboard.html', context)


# ── Products ──────────────────────────────────────────────────────────────────

@login_required
def product_list(request):
    query = request.GET.get('q', '')
    products = Product.objects.all()
    if query:
        products = products.filter(name__icontains=query) | products.filter(sku__icontains=query)
    return render(request, 'inventory/product_list.html', {
        'products': products,
        'query': query,
        'title': 'Products',
    })


@login_required
def product_create(request):
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            product = form.save()
            _log(request.user, 'create', product, f"SKU={product.sku}, qty={product.quantity}")
            messages.success(request, f'Product "{product.name}" added.')
            return redirect('product_list')
    else:
        form = ProductForm()
    return render(request, 'inventory/product_form.html', {'form': form, 'title': 'Add Product'})


@login_required
def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    movements = (
        InventoryMovement.objects
        .filter(product=product)
        .select_related('destination_branch', 'created_by')
        .order_by('-created_at')
    )
    production_batches = movements.filter(movement_type='production_in')
    total_produced  = production_batches.aggregate(total=Sum('quantity'))['total'] or 0
    total_delivered = movements.filter(movement_type='delivery_out').aggregate(total=Sum('quantity'))['total'] or 0
    total_returned  = movements.filter(movement_type='return_in').aggregate(total=Sum('quantity'))['total'] or 0
    total_lost      = movements.filter(movement_type='loss').aggregate(total=Sum('quantity'))['total'] or 0

    can_see_recon = _has_role(request.user, 'admin', 'accountant')
    sales = None
    total_sold = 0
    if can_see_recon:
        sales = RetailerSales.objects.filter(product=product).select_related('branch').order_by('-sales_date')
        total_sold = sales.aggregate(total=Sum('sold_quantity'))['total'] or 0

    return render(request, 'inventory/product_detail.html', {
        'product': product,
        'movements': movements,
        'production_batches': production_batches,
        'total_produced': total_produced,
        'total_delivered': total_delivered,
        'total_returned': total_returned,
        'total_lost': total_lost,
        'can_see_recon': can_see_recon,
        'sales': sales,
        'total_sold': total_sold,
        'is_admin': _has_role(request.user, 'admin'),
        'today': timezone.now().date(),
        'seven_days': timezone.now().date() + timezone.timedelta(days=7),
        'title': product.name,
    })


@login_required
def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            changes = _diff(form)
            form.save()
            _log(request.user, 'update', product, changes or 'No changes')
            messages.success(request, f'Product "{product.name}" updated.')
            return redirect('product_list')
    else:
        form = ProductForm(instance=product)
    return render(request, 'inventory/product_form.html', {
        'form': form, 'title': 'Edit Product', 'product': product,
    })


@login_required
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        if product.quantity > 0:
            messages.error(request, f'Cannot delete product with remaining stock. Current quantity: {product.quantity} {product.unit}.')
            return redirect('product_detail', pk=product.pk)
        _log(request.user, 'delete', product, f"SKU={product.sku}")
        product.delete()
        messages.success(request, 'Product deleted.')
        return redirect('product_list')
    return render(request, 'inventory/product_confirm_delete.html', {
        'object': product, 'title': 'Delete Product',
    })


# ── Movements ─────────────────────────────────────────────────────────────────

@login_required
def movement_list(request):
    movements = (
        InventoryMovement.objects
        .select_related('product', 'created_by', 'destination_branch')
        .annotate(
            has_reconciliation=Exists(RetailerSales.objects.filter(delivery_movement=OuterRef('pk'))),
            has_pending_recon=Exists(RetailerSales.objects.filter(delivery_movement=OuterRef('pk'), reconciled=False)),
        )
        .order_by('-created_at')
    )

    movement_type = request.GET.get('type', '')
    branch_id     = request.GET.get('branch', '')
    product_id    = request.GET.get('product', '')
    reference     = request.GET.get('ref', '').strip()

    if movement_type:
        movements = movements.filter(movement_type=movement_type)
    if branch_id:
        movements = movements.filter(destination_branch_id=branch_id)
    if product_id:
        movements = movements.filter(product_id=product_id)
    if reference:
        movements = movements.filter(reference_no__icontains=reference)

    return render(request, 'inventory/movement_list.html', {
        'movements': movements,
        'movement_type': movement_type,
        'movement_choices': InventoryMovement.MOVEMENT_TYPES,
        'branches': Branch.objects.order_by('name'),
        'products': Product.objects.order_by('name'),
        'branch_id': branch_id,
        'product_id': product_id,
        'reference': reference,
        'has_filters': any([movement_type, branch_id, product_id, reference]),
        'title': 'Stock Movements',
    })


@login_required
@require_role('admin', 'warehouse', 'sales')
def movement_create(request):
    movement_type = request.POST.get('movement_type') or request.GET.get('type', '')

    if not movement_type:
        allowed = [t for t, roles in _TYPE_ROLES.items() if _has_role(request.user, *roles)]
        return render(request, 'inventory/movement_type_select.html', {'allowed_types': allowed, 'title': 'Record Movement'})

    if movement_type not in _MOVEMENT_FORMS:
        messages.error(request, 'Invalid movement type.')
        return redirect('movement_create')
    if not _has_role(request.user, *_TYPE_ROLES[movement_type]):
        messages.error(request, 'You are not permitted to record this movement type.')
        return redirect('movement_create')

    FormClass = _MOVEMENT_FORMS[movement_type]

    if request.method == 'POST':
        form = FormClass(request.POST, user=request.user)
        if form.is_valid():
            movement = form.save(commit=False)
            movement.movement_type = movement_type
            movement.created_by = request.user
            if movement_type == 'back_order':
                movement.back_order_status = 'pending'
            movement.save()
            if movement_type == 'delivery_out' and movement.closes_back_order:
                bo_qty = movement.closes_back_order.quantity
                remainder = _handle_back_order_fulfillment(movement, request.user)
                if remainder:
                    messages.warning(request, f"Partial delivery: {movement.quantity} of {bo_qty} delivered. A new back order for the remaining {remainder} has been created automatically.")
            _log(request.user, 'create', movement, f"type={movement_type}, qty={movement.quantity}, product={movement.product}")
            messages.success(request, 'Movement recorded.')
            return redirect('movement_list')
    else:
        form = FormClass(user=request.user)

    return render(request, 'inventory/movement_form.html', {'form': form, 'movement_type': movement_type, 'title': f"Record — {dict(InventoryMovement.MOVEMENT_TYPES).get(movement_type, movement_type)}"})


@login_required
@require_role('admin', 'warehouse')
def batch_list(request):
    batches = (
        InventoryMovement.objects
        .filter(movement_type='production_in')
        .select_related('product', 'created_by')
        .order_by('-created_at')
    )

    return render(request, 'inventory/batch_list.html', {
        'batches': batches,
        'today': timezone.now().date(),
        'seven_days': timezone.now().date() + timezone.timedelta(days=7),
        'title': 'Batches',
    })


@login_required
def batches_for_product(request):
    product_id = request.GET.get('product_id')
    if not product_id:
        return JsonResponse({'batches': []})
    batches = InventoryMovement.objects.filter(
        product_id=product_id,
        movement_type='production_in',
    ).order_by('expiration_date')
    result = []
    for b in batches:
        avail = b.available_quantity()
        if avail > 0:
            result.append({
                'id': b.pk,
                'label': f"{b.batch_number} — exp {b.expiration_date} ({avail} {b.product.unit} available)",
                'available': avail,
            })
    return JsonResponse({'batches': result})


@login_required
def deliveries_for_loss(request):
    product_id = request.GET.get('product_id')
    if not product_id:
        return JsonResponse({'deliveries': []})
    qs = (
        InventoryMovement.objects
        .filter(product_id=product_id, movement_type='delivery_out')
        .select_related('product', 'destination_branch')
        .order_by('-created_at')
    )
    result = [
        {
            'id': m.pk,
            'label': (
                f"{m.reference_no or 'No ref'} → {m.destination_branch or '?'}"
                f" ({m.quantity} {m.product.unit}, {m.created_at.strftime('%b %d, %Y')})"
            ),
        }
        for m in qs
    ]
    return JsonResponse({'deliveries': result})


@login_required
def delivery_details(request):
    movement_id = request.GET.get('movement_id')
    if not movement_id:
        return JsonResponse({})
    try:
        m = InventoryMovement.objects.select_related('product', 'destination_branch').get(
            pk=movement_id, movement_type='delivery_out'
        )
    except InventoryMovement.DoesNotExist:
        return JsonResponse({})
    return JsonResponse({
        'product_id': m.product_id,
        'product_name': m.product.name,
        'branch_id': m.destination_branch_id,
        'branch_name': str(m.destination_branch) if m.destination_branch else '',
        'qty': m.quantity,
        'reference_no': m.reference_no or '',
    })


# ── Reconciliation ────────────────────────────────────────────────────────────

@login_required
@require_role('admin', 'accountant')
def reconciliation_list(request):
    reconciliations = RetailerSales.objects.select_related('product', 'branch').order_by('-sales_date')

    branch_id  = request.GET.get('branch', '')
    product_id = request.GET.get('product', '')
    status     = request.GET.get('status', '')
    date_from  = request.GET.get('date_from', '')
    date_to    = request.GET.get('date_to', '')

    if branch_id:              reconciliations = reconciliations.filter(branch_id=branch_id)
    if product_id:             reconciliations = reconciliations.filter(product_id=product_id)
    if status == 'reconciled': reconciliations = reconciliations.filter(reconciled=True)
    elif status == 'pending':  reconciliations = reconciliations.filter(reconciled=False)
    if date_from:              reconciliations = reconciliations.filter(sales_date__gte=date_from)
    if date_to:                reconciliations = reconciliations.filter(sales_date__lte=date_to)

    total_discrepancy = reconciliations.aggregate(total=Sum('discrepancy'))['total'] or 0
    reconciled_count  = reconciliations.filter(reconciled=True).count()

    return render(request, 'inventory/reconciliation_list.html', {
        'reconciliations': reconciliations,
        'total_discrepancy': total_discrepancy,
        'reconciled_count': reconciled_count,
        'branches': Branch.objects.order_by('name'),
        'products': Product.objects.order_by('name'),
        'branch_id': branch_id,
        'product_id': product_id,
        'status': status,
        'date_from': date_from,
        'date_to': date_to,
        'has_filters': any([branch_id, product_id, status, date_from, date_to]),
        'title': 'Stock Reconciliation',
    })


@login_required
@require_role('admin', 'accountant')
def reconciliation_resolve(request, pk):
    record = get_object_or_404(RetailerSales, pk=pk)

    if record.reconciled or record.resolution_status != 'pending':
        messages.info(request, 'This record is already resolved.')
        return redirect('reconciliation_list')

    if request.method == 'POST':
        form = ReconciliationResolveForm(request.POST, internal_delivery_qty=record.internal_delivery_qty)
        if form.is_valid():
            record.resolution_status = form.cleaned_data['resolution_status']
            record.resolution_note = form.cleaned_data['resolution_note']
            record.resolved_by = request.user
            record.resolved_at = timezone.now()
            record.reconciled = True

            status = form.cleaned_data['resolution_status']

            # no stock movement for any resolution — goods are gone once delivered
            record.save()
            _log(request.user, 'update', record,
                 f"resolved_as={record.resolution_status}, note={record.resolution_note}")

            if status == 'corrected':
                corrected_qty = form.cleaned_data['corrected_sold_quantity']
                new_record = RetailerSales.objects.create(
                    product=record.product,
                    branch=record.branch,
                    delivery_movement=record.delivery_movement,
                    sold_quantity=corrected_qty,
                    sales_date=record.sales_date,
                    internal_delivery_qty=record.internal_delivery_qty,
                )
                _log(request.user, 'create', new_record,
                     f"auto-created corrected entry from recon #{record.pk}, corrected_qty={corrected_qty}")
                messages.success(request, f'Record corrected. A new entry with {corrected_qty} {record.product.unit} sold has been created.')
            else:
                messages.success(request, f'Discrepancy marked as resolved ({record.get_resolution_status_display()}).')
            return redirect('reconciliation_list')
    else:
        form = ReconciliationResolveForm(internal_delivery_qty=record.internal_delivery_qty)

    return render(request, 'inventory/reconciliation_resolve.html', {
        'form': form,
        'record': record,
        'discrepancy': record.discrepancy or 0,
        'title': 'Resolve Discrepancy',
    })


@login_required
@require_role('admin', 'accountant')
def reconciliation_add(request):
    if request.method == 'POST':
        form = RetailerSalesForm(request.POST)
        if form.is_valid():
            if request.POST.get('confirmed') != '1':
                cd = form.cleaned_data
                discrepancy = (cd['internal_delivery_qty'] - cd['sold_quantity']) if cd.get('internal_delivery_qty') else None
                return render(request, 'inventory/reconciliation_confirm.html', {
                    'form': form, 'cd': cd, 'discrepancy': discrepancy, 'title': 'Confirm Sales Data',
                })
            record = form.save()
            _log(request.user, 'create', record,
                 f"branch={record.branch}, product={record.product}, sold={record.sold_quantity}, "
                 f"delivery={record.internal_delivery_qty}, discrepancy={record.discrepancy}")
            messages.success(request, 'Retailer sales data added.')
            return redirect('reconciliation_list')
    else:
        form = RetailerSalesForm()
    return render(request, 'inventory/reconciliation_form.html', {'form': form, 'title': 'Add Retailer Sales'})


# ── Sales Summary ─────────────────────────────────────────────────────────────

@login_required
@require_role('admin', 'accountant')
def sales_summary(request):
    by_product = (
        RetailerSales.objects
        .values('product__name', 'product__sku', 'product__unit')
        .annotate(total_sold=Sum('sold_quantity'))
        .order_by('-total_sold')
    )
    by_branch = (
        RetailerSales.objects
        .values('branch__name')
        .annotate(total_sold=Sum('sold_quantity'))
        .order_by('-total_sold')
    )
    delivered_by_product = (
        InventoryMovement.objects
        .filter(movement_type='delivery_out')
        .values('product__name', 'product__sku', 'product__unit')
        .annotate(total_delivered=Sum('quantity'))
    )
    delivered_by_branch = (
        InventoryMovement.objects
        .filter(movement_type='delivery_out')
        .values('destination_branch__name')
        .annotate(total_delivered=Sum('quantity'))
    )
    grand_total = by_product.aggregate(total=Sum('total_sold'))['total'] or 0

    return render(request, 'inventory/sales_summary.html', {
        'by_product': by_product,
        'by_branch': by_branch,
        'delivered_by_product': delivered_by_product,
        'delivered_by_branch': delivered_by_branch,
        'grand_total': grand_total,
        'title': 'Consignment Summary',
    })


# ── Reports ───────────────────────────────────────────────────────────────────

@login_required
def reports(request):
    total_loss_qty = (
        InventoryMovement.objects.filter(movement_type='loss')
        .aggregate(total=Sum('quantity'))['total'] or 0
    )
    product_losses = (
        InventoryMovement.objects
        .filter(movement_type='loss')
        .values('product__name', 'product__sku', 'product__unit')
        .annotate(total_lost=Sum('quantity'))
        .order_by('-total_lost')
    )
    deliveries_by_branch = (
        InventoryMovement.objects
        .filter(movement_type='delivery_out')
        .values('destination_branch__name')
        .annotate(total_qty=Sum('quantity'), total_movements=Count('id'))
        .order_by('-total_qty')
    )
    unreturned_unsold = (
        RetailerSales.objects
        .filter(reconciled=True, discrepancy__gt=0)
        .exclude(resolution_status='returned')
        .values('product__name', 'product__sku', 'product__unit')
        .annotate(total_lost=Sum('discrepancy'))
        .order_by('-total_lost')
    )
    back_orders = InventoryMovement.objects.filter(movement_type='back_order').select_related('product', 'created_by', 'destination_branch').order_by('-created_at')
    unreconciled = RetailerSales.objects.filter(reconciled=False).count()
    reconciled = RetailerSales.objects.filter(reconciled=True).count()
    
    total_loss_qty += unreturned_unsold.aggregate(total=Sum('total_lost'))['total'] or 0

    return render(request, 'inventory/reports.html', {
        'title': 'Reports',
        'total_loss_qty': total_loss_qty,
        'product_losses': product_losses,
        'deliveries_by_branch': deliveries_by_branch,
        'unreturned_unsold': unreturned_unsold,
        'back_orders': back_orders,
        'unreconciled': unreconciled,
        'reconciled': reconciled,
    })


# ── Audit Log ─────────────────────────────────────────────────────────────────

@login_required
@require_role('admin')
def audit_log(request):
    logs = AuditLog.objects.select_related('user').order_by('-timestamp')

    action_filter = request.GET.get('action', '')
    model_filter  = request.GET.get('model', '')
    date_from     = request.GET.get('date_from', '')
    date_to       = request.GET.get('date_to', '')

    if action_filter: logs = logs.filter(action=action_filter)
    if model_filter:  logs = logs.filter(model_name=model_filter)
    if date_from:     logs = logs.filter(timestamp__date__gte=date_from)
    if date_to:       logs = logs.filter(timestamp__date__lte=date_to)

    model_names = AuditLog.objects.values_list('model_name', flat=True).distinct()

    return render(request, 'inventory/audit_log.html', {
        'title': 'Audit Log',
        'logs': logs[:200],
        'action_filter': action_filter,
        'model_filter': model_filter,
        'date_from': date_from,
        'date_to': date_to,
        'model_names': model_names,
        'action_choices': AuditLog.ACTION_CHOICES,
        'has_filters': any([action_filter, model_filter, date_from, date_to]),
    })


# ── User Management (admin only) ──────────────────────────────────────────────

@login_required
@require_role('admin')
def user_management(request):
    users = User.objects.select_related('profile').all()
    return render(request, 'inventory/user_management.html', {'users': users, 'title': 'User Management'})


@login_required
@require_role('admin')
def user_create(request):
    if request.method == 'POST':
        form = UserCreateForm(request.POST)
        if form.is_valid():
            new_user = form.save()
            _log(request.user, 'create', new_user,
                 f"role={form.cleaned_data['role']}")
            messages.success(request, f'User "{new_user.username}" created.')
            return redirect('user_management')
    else:
        form = UserCreateForm()
    return render(request, 'inventory/user_form.html', {'form': form, 'title': 'Create User'})


@login_required
@require_role('admin')
def user_edit(request, pk):
    target_user = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        form = UserEditForm(request.POST, instance=target_user)
        if form.is_valid():
            changes = _diff(form)
            form.save()
            _log(request.user, 'update', target_user, changes or 'No changes')
            messages.success(request, f'User "{target_user.username}" updated.')
            return redirect('user_management')
    else:
        form = UserEditForm(instance=target_user)
    return render(request, 'inventory/user_form.html', {
        'form': form, 'title': 'Edit User', 'edit_user': target_user,
    })


@login_required
@require_role('admin')
def user_deactivate(request, pk):
    target_user = get_object_or_404(User, pk=pk)

    if target_user == request.user:
        messages.error(request, 'You cannot deactivate your own account.')
        return redirect('user_management')
    if target_user.is_superuser:
        messages.error(request, 'Superuser accounts cannot be deactivated.')
        return redirect('user_management')

    if request.method == 'POST':
        target_user.is_active = not target_user.is_active
        target_user.save()
        action_label = 'activated' if target_user.is_active else 'deactivated'
        _log(request.user, 'update', target_user, f"is_active set to {target_user.is_active}")
        messages.success(request, f'User "{target_user.username}" {action_label}.')
        return redirect('user_management')

    return render(request, 'inventory/user_confirm_deactivate.html', {
        'target_user': target_user,
        'title': 'Deactivate User' if target_user.is_active else 'Activate User',
    })


@login_required
@require_role('admin')
def user_delete(request, pk):
    target_user = get_object_or_404(User, pk=pk)

    if target_user == request.user:
        messages.error(request, 'You cannot delete your own account.')
        return redirect('user_management')
    if target_user.is_superuser:
        messages.error(request, 'Superuser accounts cannot be deleted here.')
        return redirect('user_management')

    if request.method == 'POST':
        username = target_user.username
        _log(request.user, 'delete', target_user, f"username={username}")
        target_user.delete()
        messages.success(request, f'User "{username}" deleted.')
        return redirect('user_management')

    return render(request, 'inventory/user_confirm_delete.html', {
        'target_user': target_user,
        'title': 'Delete User',
    })


# ── Branches ──────────────────────────────────────────────────────────────────

@login_required
def branch_list(request):
    branches = Branch.objects.all()
    return render(request, 'inventory/branch_list.html', {
        'branches': branches,
        'title': 'Branches',
        'is_admin': _has_role(request.user, 'admin'),
    })


@login_required
@require_role('admin')
def branch_create(request):
    if request.method == 'POST':
        form = BranchForm(request.POST)
        if form.is_valid():
            branch = form.save()
            _log(request.user, 'create', branch, f"name={branch.name}")
            messages.success(request, f'Branch "{branch.name}" added.')
            return redirect('branch_list')
    else:
        form = BranchForm()
    return render(request, 'inventory/branch_form.html', {'form': form, 'title': 'Add Branch'})


@login_required
@require_role('admin')
def branch_edit(request, pk):
    branch = get_object_or_404(Branch, pk=pk)
    if request.method == 'POST':
        form = BranchForm(request.POST, instance=branch)
        if form.is_valid():
            changes = _diff(form)
            form.save()
            _log(request.user, 'update', branch, changes or 'No changes')
            messages.success(request, f'Branch "{branch.name}" updated.')
            return redirect('branch_list')
    else:
        form = BranchForm(instance=branch)
    return render(request, 'inventory/branch_form.html', {
        'form': form, 'title': 'Edit Branch', 'branch': branch,
    })


@login_required
@require_role('admin')
def branch_delete(request, pk):
    branch = get_object_or_404(Branch, pk=pk)
    if request.method == 'POST':
        _log(request.user, 'delete', branch, f"name={branch.name}")
        branch.delete()
        messages.success(request, f'Branch "{branch.name}" deleted.')
        return redirect('branch_list')
    return render(request, 'inventory/branch_confirm_delete.html', {
        'branch': branch, 'title': 'Delete Branch',
    })


@login_required
def branch_detail(request, pk):
    branch = get_object_or_404(Branch, pk=pk)
    movements = (
        InventoryMovement.objects
        .filter(destination_branch=branch)
        .select_related('product', 'created_by')
        .order_by('-created_at')
    )
    total_delivered = movements.filter(movement_type='delivery_out').aggregate(total=Sum('quantity'))['total'] or 0
    total_back_orders = movements.filter(movement_type='back_order').aggregate(total=Sum('quantity'))['total'] or 0

    can_see_reconciliation = _has_role(request.user, 'admin', 'accountant')
    sales = None
    total_sold = 0
    total_discrepancy = 0
    if can_see_reconciliation:
        sales = RetailerSales.objects.filter(branch=branch).select_related('product').order_by('-sales_date')
        total_sold = sales.aggregate(total=Sum('sold_quantity'))['total'] or 0
        total_discrepancy = sales.aggregate(total=Sum('discrepancy'))['total'] or 0

    return render(request, 'inventory/branch_detail.html', {
        'branch': branch,
        'movements': movements,
        'total_delivered': total_delivered,
        'total_back_orders': total_back_orders,
        'can_see_reconciliation': can_see_reconciliation,
        'sales': sales,
        'total_sold': total_sold,
        'total_discrepancy': total_discrepancy,
        'is_admin': _has_role(request.user, 'admin'),
        'title': branch.name,
    })


# ── User Profile ──────────────────────────────────────────────────────────────

@login_required
def user_profile(request):
    def _styled(form):
        for f in form.fields.values():
            f.widget.attrs.setdefault('class', 'form-control')
        return form

    profile_form = _styled(ProfileForm(instance=request.user))
    password_form = _styled(PasswordChangeForm(request.user))

    if request.method == 'POST':
        form_type = request.POST.get('form_type')
        if form_type == 'profile':
            profile_form = _styled(ProfileForm(request.POST, instance=request.user))
            if profile_form.is_valid():
                changes = _diff(profile_form)
                profile_form.save()
                _log(request.user, 'update', request.user, changes or 'Profile updated')
                messages.success(request, 'Profile updated.')
                return redirect('user_profile')
        elif form_type == 'password':
            password_form = _styled(PasswordChangeForm(request.user, request.POST))
            if password_form.is_valid():
                password_form.save()
                update_session_auth_hash(request, password_form.user)
                messages.success(request, 'Password changed successfully.')
                return redirect('user_profile')

    return render(request, 'inventory/profile.html', {
        'profile_form': profile_form,
        'password_form': password_form,
        'profile': getattr(request.user, 'profile', None),
        'title': 'My Profile',
    })


# ── Auth ──────────────────────────────────────────────────────────────────────

def user_login(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            return redirect('dashboard')
        messages.error(request, 'Invalid username or password.')
    else:
        form = AuthenticationForm()
    return render(request, 'inventory/login.html', {'form': form})


@login_required
def user_logout(request):
    logout(request)
    return redirect('user_login')
