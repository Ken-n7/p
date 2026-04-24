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

    # Reports
    path('reports/', views.reports, name='reports'),

    # Audit log (admin only)
    path('audit/', views.audit_log, name='audit_log'),

    # User management (admin only)
    path('users/', views.user_management, name='user_management'),
    path('users/add/', views.user_create, name='user_create'),
    path('users/<int:pk>/edit/', views.user_edit, name='user_edit'),

    # Auth
    path('login/', views.user_login, name='user_login'),
    path('logout/', views.user_logout, name='user_logout'),
]
