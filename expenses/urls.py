from django.urls import path

from . import views

app_name = 'expenses'

urlpatterns = [
    path('<int:group_id>/expenses/new/', views.expense_create, name='create'),
    path('<int:group_id>/expenses/<int:expense_id>/delete/', views.expense_delete, name='delete'),
]