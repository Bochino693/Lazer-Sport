from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from core.views import media_serve

urlpatterns = [
    path('system/', admin.site.urls),
    # MEDIA FORÇADO (produção)
    path('media/<path:path>/', media_serve),

    path('', include('core.urls')),
]


