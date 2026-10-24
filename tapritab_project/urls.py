from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from groups.views import home

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('accounts/', include('accounts.urls')),
    path('groups/', include('groups.urls')),
    path('groups/', include('expenses.urls')),
    path('api/', include('api.urls')),
    path('api-auth/', include('rest_framework.urls')),
    path('', home, name='home'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
