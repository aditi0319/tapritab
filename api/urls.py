from django.urls import path

from . import views

app_name = 'api'

urlpatterns = [
    path('groups/', views.GroupListView.as_view(), name='group_list'),
    path('groups/<int:group_id>/', views.GroupDetailView.as_view(), name='group_detail'),
    path('groups/<int:group_id>/expenses/', views.ExpenseListCreateView.as_view(), name='expense_list'),
    path('groups/<int:group_id>/balances/', views.BalanceView.as_view(), name='balances'),
]
