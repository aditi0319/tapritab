from django.urls import path

from . import views

app_name = 'expenses'

urlpatterns = [
    path('<int:group_id>/expenses/new/', views.expense_create, name='create'),
    path('<int:group_id>/expenses/<int:expense_id>/delete/', views.expense_delete, name='delete'),
    path('<int:group_id>/expenses/quick/', views.quick_add, name='quick_add'),
    path('<int:group_id>/settle/', views.settle_up, name='settle_up'),
    path('<int:group_id>/settle/record/', views.settlement_create, name='settlement_create'),
    path('<int:group_id>/settle/<int:settlement_id>/confirm/', views.settlement_confirm, name='settlement_confirm'),
    path('<int:group_id>/settle/<int:settlement_id>/cancel/', views.settlement_cancel, name='settlement_cancel'),
]
