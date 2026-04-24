from django.shortcuts import render, redirect
from django.utils import timezone

from .models import Product, InventoryMovement
from .forms import ProductForm
from .models import InventoryMovement
from .forms import InventoryMovementForm   # we'll create this next
from .models import RetailerSales
from .forms import RetailerSalesForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

@login_required
def dashboard(request):
    profile = request.user.profile if hasattr(request.user, 'profile') else None
    role = profile.role if profile else 'admin'

    total_products = Product.objects.count()
    low_stock = Product.objects.filter(quantity__lt=10)[:5]
    near_expiry = Product.objects.filter(
        expiration_date__isnull=False,
        expiration_date__lte=timezone.now().date() + timezone.timedelta(days=7)
    )[:5]
    recent_movements = InventoryMovement.objects.all().order_by('-created_at')[:5]
    
    context = {
        'total_products': total_products,
        'low_stock_count': low_stock.count(),
        'low_stock': low_stock,
        'near_expiry_count': near_expiry.count(),
        'near_expiry': near_expiry,
        'recent_movements': recent_movements,
        'user_role': role,
        'title': 'Dashboard - Supply Chain Match'
    }
    return render(request, 'inventory/dashboard.html', context)

def dashboard(request):
    total_products = Product.objects.count()
    low_stock = Product.objects.filter(quantity__lt=10)
    near_expiry = Product.objects.filter(
        expiration_date__isnull=False,
        expiration_date__lte=timezone.now().date() + timezone.timedelta(days=7)
    )
    recent_movements = InventoryMovement.objects.all().order_by('-created_at')[:5]
    
    context = {
        'total_products': total_products,
        'low_stock_count': low_stock.count(),
        'low_stock': low_stock[:5],
        'near_expiry_count': near_expiry.count(),
        'near_expiry': near_expiry[:5],
        'recent_movements': recent_movements,
        'title': 'Dashboard - Supply Chain Match'
    }
    return render(request, 'inventory/dashboard.html', context)


def product_list(request):
    products = Product.objects.all()
    context = {
        'products': products,
        'title': 'Products'
    }
    return render(request, 'inventory/product_list.html', context)


def product_create(request):
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('product_list')
    else:
        form = ProductForm()
    
    context = {
        'form': form,
        'title': 'Add New Product'
    }
    return render(request, 'inventory/product_form.html', context)

def movement_list(request):
    movements = InventoryMovement.objects.all().order_by('-created_at')
    context = {
        'movements': movements,
        'title': 'Stock Movements'
    }
    return render(request, 'inventory/movement_list.html', context)

def movement_create(request):
    if request.method == 'POST':
        form = InventoryMovementForm(request.POST)
        if form.is_valid():
            movement = form.save(commit=False)
            movement.created_by = request.user if request.user.is_authenticated else None
            movement.save()
            return redirect('movement_list')
    else:
        form = InventoryMovementForm()
    
    context = {
        'form': form,
        'title': 'Record New Movement'
    }
    return render(request, 'inventory/movement_form.html', context)

def reconciliation_list(request):
    reconciliations = RetailerSales.objects.all().order_by('-sales_date')
    total_discrepancy = sum(r.discrepancy or 0 for r in reconciliations)
    reconciled_count = reconciliations.filter(reconciled=True).count()
    
    context = {
        'reconciliations': reconciliations,
        'total_discrepancy': total_discrepancy,
        'reconciled_count': reconciled_count,
        'title': 'Stock Reconciliation'
    }
    return render(request, 'inventory/reconciliation_list.html', context)

def reconciliation_add(request):
    if request.method == 'POST':
        form = RetailerSalesForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('reconciliation_list')
    else:
        form = RetailerSalesForm()
    
    context = {
        'form': form,
        'title': 'Add Retailer Sales Data'
    }
    return render(request, 'inventory/reconciliation_form.html', context)

# Login View
def user_login(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('dashboard')
    else:
        form = AuthenticationForm()
    
    return render(request, 'inventory/login.html', {'form': form})

@login_required
def user_logout(request):
    logout(request)
    return redirect('user_login')