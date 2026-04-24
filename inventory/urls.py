from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('products/', views.product_list, name='product_list'),
    path('products/add/', views.product_create, name='product_create'),
    
    # New Movement URLs
    path('movements/', views.movement_list, name='movement_list'),
    path('movements/add/', views.movement_create, name='movement_create'),

    path('reconciliation/', views.reconciliation_list, name='reconciliation_list'),
    path('reconciliation/add/', views.reconciliation_add, name='reconciliation_add'),
    
    path('login/', views.user_login, name='user_login'),
    path('logout/', views.user_logout, name='user_logout'),
]