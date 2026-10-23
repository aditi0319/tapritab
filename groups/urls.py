from django.urls import path

from . import views

app_name = 'groups'

urlpatterns = [
    path('', views.group_list, name='list'),
    path('new/', views.group_create, name='create'),
    path('<int:group_id>/', views.group_detail, name='detail'),
    path('<int:group_id>/invite/reset/', views.regenerate_invite, name='regenerate_invite'),
    path('<int:group_id>/members/<int:user_id>/remove/', views.remove_member, name='remove_member'),
    path('<int:group_id>/leave/', views.leave_group, name='leave'),
    path('join/<uuid:invite_code>/', views.group_join, name='join'),
]