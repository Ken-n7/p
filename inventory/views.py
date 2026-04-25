import csv
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login, logout
from django.contrib import messages
from django.db.models import Sum, Count

from .models import Product, InventoryMovement, RetailerSales, AuditLog
from .forms import ProductForm, InventoryMovementForm, RetailerSalesForm


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_admin(user):
    if user.is_superuser:
        return True
    profile = getattr(user, 'profile', None)
    return profile and profile.role == 'admin'


def _has_role(user, *roles):
    """Return True if user is superuser or has one of the given roles."""
    if user.is_superuser:
        return True
    profile = getattr(user, 'profile', None)
    return profile and profile.role in roles


def _log(user, action, obj, changes=''):
    AuditLog.objects.create(
        user=user if user.is_authenticated else None,
        action=action,
        model_name=obj.__class__.__name__,
        object_id=obj.pk,
        object_repr=str(obj),
        changes=changes,
    )


def _diff(form):
    """Return a readable string of changed fields for an edit form."""
    if not form.changed_data:
        return ''
    from django.forms import ModelChoiceField
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
    near_expiry = Product.objects.filter(
        expiration_date__isnull=False,
        expiration_date__lte=timezone.now().date() + timezone.timedelta(days=7)
    )
    recent_movements = InventoryMovement.objects.select_related('product', 'created_by').order_by('-created_at')[:10]

    context = {
        'total_products': total_products,
        'total_movements': total_movements,
        'low_stock_count': low_stock.count(),
        'low_stock': low_stock[:5],
        'near_expiry_count': near_expiry.count(),
        'near_expiry': near_expiry[:5],
        'recent_movements': recent_movements,
        'user_role': role,
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
    movements = InventoryMovement.objects.select_related('product', 'created_by').order_by('-created_at')
    movement_type = request.GET.get('type', '')
    if movement_type:
        movements = movements.filter(movement_type=movement_type)
    return render(request, 'inventory/movement_list.html', {
        'movements': movements,
        'movement_type': movement_type,
        'movement_choices': InventoryMovement.MOVEMENT_TYPES,
        'title': 'Stock Movements',
    })


@login_required
def movement_create(request):
    if not _has_role(request.user, 'admin', 'warehouse', 'sales'):
        messages.error(request, 'Access denied. Recording movements is for admin, warehouse, and sales roles only.')
        return redirect('movement_list')
    if request.method == 'POST':
        form = InventoryMovementForm(request.POST)
        if form.is_valid():
            movement = form.save(commit=False)
            movement.created_by = request.user
            movement.save()
            _log(request.user, 'create', movement,
                 f"type={movement.movement_type}, qty={movement.quantity}, product={movement.product}")
            messages.success(request, 'Movement recorded.')
            return redirect('movement_list')
    else:
        form = InventoryMovementForm()
    return render(request, 'inventory/movement_form.html', {'form': form, 'title': 'Record Movement'})


# ── Reconciliation ────────────────────────────────────────────────────────────

@login_required
def reconciliation_list(request):
    if not _has_role(request.user, 'admin', 'accountant'):
        messages.error(request, 'Access denied. Reconciliation is for admin and accountant roles only.')
        return redirect('dashboard')
    reconciliations = RetailerSales.objects.select_related('product').order_by('-sales_date')
    total_discrepancy = sum(r.discrepancy or 0 for r in reconciliations)
    reconciled_count = reconciliations.filter(reconciled=True).count()
    return render(request, 'inventory/reconciliation_list.html', {
        'reconciliations': reconciliations,
        'total_discrepancy': total_discrepancy,
        'reconciled_count': reconciled_count,
        'title': 'Stock Reconciliation',
    })


@login_required
def reconciliation_add(request):
    if not _has_role(request.user, 'admin', 'accountant'):
        messages.error(request, 'Access denied. Reconciliation is for admin and accountant roles only.')
        return redirect('dashboard')
    if request.method == 'POST':
        form = RetailerSalesForm(request.POST)
        if form.is_valid():
            record = form.save()
            _log(request.user, 'create', record,
                 f"branch={record.branch}, product={record.product}, sold={record.sold_quantity}, "
                 f"delivery={record.internal_delivery_qty}, discrepancy={record.discrepancy}")
            messages.success(request, 'Retailer sales data added.')
            return redirect('reconciliation_list')
    else:
        form = RetailerSalesForm()
    return render(request, 'inventory/reconciliation_form.html', {'form': form, 'title': 'Add Retailer Sales'})


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
        .values('product__name', 'product__sku')
        .annotate(total_lost=Sum('quantity'))
        .order_by('-total_lost')
    )
    deliveries_by_branch = (
        InventoryMovement.objects
        .filter(movement_type='delivery_out')
        .values('destination_branch')
        .annotate(total_qty=Sum('quantity'), total_movements=Count('id'))
        .order_by('-total_qty')
    )
    back_orders = InventoryMovement.objects.filter(movement_type='back_order').order_by('-created_at')
    unreconciled = RetailerSales.objects.filter(reconciled=False).count()
    reconciled = RetailerSales.objects.filter(reconciled=True).count()

    return render(request, 'inventory/reports.html', {
        'title': 'Reports',
        'total_loss_qty': total_loss_qty,
        'product_losses': product_losses,
        'deliveries_by_branch': deliveries_by_branch,
        'back_orders': back_orders,
        'unreconciled': unreconciled,
        'reconciled': reconciled,
    })


# ── CSV Exports ───────────────────────────────────────────────────────────────

@login_required
def export_losses_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="loss_analysis.csv"'
    writer = csv.writer(response)
    writer.writerow(['Product', 'SKU', 'Total Lost (units)'])
    rows = (
        InventoryMovement.objects
        .filter(movement_type='loss')
        .values('product__name', 'product__sku')
        .annotate(total_lost=Sum('quantity'))
        .order_by('-total_lost')
    )
    for row in rows:
        writer.writerow([row['product__name'], row['product__sku'], row['total_lost']])
    return response


@login_required
def export_deliveries_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="deliveries_by_branch.csv"'
    writer = csv.writer(response)
    writer.writerow(['Branch', 'Number of Deliveries', 'Total Quantity'])
    rows = (
        InventoryMovement.objects
        .filter(movement_type='delivery_out')
        .values('destination_branch')
        .annotate(total_qty=Sum('quantity'), total_movements=Count('id'))
        .order_by('-total_qty')
    )
    for row in rows:
        writer.writerow([row['destination_branch'] or '(unspecified)', row['total_movements'], row['total_qty']])
    return response


@login_required
def export_back_orders_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="back_orders.csv"'
    writer = csv.writer(response)
    writer.writerow(['Date', 'Product', 'Quantity', 'Branch', 'Reference', 'Note', 'Recorded By'])
    back_orders = InventoryMovement.objects.filter(movement_type='back_order').select_related('product', 'created_by').order_by('-created_at')
    for m in back_orders:
        writer.writerow([
            m.created_at.strftime('%Y-%m-%d %H:%M'),
            m.product.name,
            m.quantity,
            m.destination_branch or '',
            m.reference_no or '',
            m.note or '',
            m.created_by.username if m.created_by else '',
        ])
    return response


# ── Audit Log ─────────────────────────────────────────────────────────────────

@login_required
def audit_log(request):
    if not _is_admin(request.user):
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    logs = AuditLog.objects.select_related('user').order_by('-timestamp')

    # Optional filters
    action_filter = request.GET.get('action', '')
    model_filter = request.GET.get('model', '')
    if action_filter:
        logs = logs.filter(action=action_filter)
    if model_filter:
        logs = logs.filter(model_name=model_filter)

    model_names = AuditLog.objects.values_list('model_name', flat=True).distinct()

    return render(request, 'inventory/audit_log.html', {
        'title': 'Audit Log',
        'logs': logs[:200],
        'action_filter': action_filter,
        'model_filter': model_filter,
        'model_names': model_names,
        'action_choices': AuditLog.ACTION_CHOICES,
    })


# ── User Management (admin only) ──────────────────────────────────────────────

@login_required
def user_management(request):
    from django.contrib.auth.models import User
    if not _is_admin(request.user):
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    users = User.objects.select_related('profile').all()
    return render(request, 'inventory/user_management.html', {'users': users, 'title': 'User Management'})


@login_required
def user_create(request):
    from .forms import UserCreateForm
    if not _is_admin(request.user):
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

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
def user_edit(request, pk):
    from django.contrib.auth.models import User
    from .forms import UserEditForm
    if not _is_admin(request.user):
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

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
def user_deactivate(request, pk):
    from django.contrib.auth.models import User
    if not _is_admin(request.user):
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

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
def user_delete(request, pk):
    from django.contrib.auth.models import User
    if not _is_admin(request.user):
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

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
