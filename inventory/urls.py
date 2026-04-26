from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),

    # Products
    path('products/', views.product_list, name='product_list'),
    path('products/add/', views.product_create, name='product_create'),
    path('products/<int:pk>/edit/', views.product_edit, name='product_edit'),
    path('products/<int:pk>/delete/', views.product_delete, name='product_delete'),

    # Movements
    path('movements/', views.movement_list, name='movement_list'),
    path('movements/add/', views.movement_create, name='movement_create'),

    # Reconciliation
    path('reconciliation/', views.reconciliation_list, name='reconciliation_list'),
    path('reconciliation/add/', views.reconciliation_add, name='reconciliation_add'),
    path('reconciliation/<int:pk>/resolve/', views.reconciliation_resolve, name='reconciliation_resolve'),
    path('sales-summary/', views.sales_summary, name='sales_summary'),

    # Branches
    path('branches/', views.branch_list, name='branch_list'),
    path('branches/add/', views.branch_create, name='branch_create'),
    path('branches/<int:pk>/', views.branch_detail, name='branch_detail'),
    path('branches/<int:pk>/edit/', views.branch_edit, name='branch_edit'),
    path('branches/<int:pk>/delete/', views.branch_delete, name='branch_delete'),

    # Reports
    path('reports/', views.reports, name='reports'),
    path('reports/export/losses/', views.export_losses_csv, name='export_losses_csv'),
    path('reports/export/deliveries/', views.export_deliveries_csv, name='export_deliveries_csv'),
    path('reports/export/back-orders/', views.export_back_orders_csv, name='export_back_orders_csv'),

    # Audit log (admin only)
    path('audit/', views.audit_log, name='audit_log'),

    # User management (admin only)
    path('users/', views.user_management, name='user_management'),
    path('users/add/', views.user_create, name='user_create'),
    path('users/<int:pk>/edit/', views.user_edit, name='user_edit'),
    path('users/<int:pk>/deactivate/', views.user_deactivate, name='user_deactivate'),
    path('users/<int:pk>/delete/', views.user_delete, name='user_delete'),

    # Auth
    path('login/', views.user_login, name='user_login'),
    path('logout/', views.user_logout, name='user_logout'),
]
