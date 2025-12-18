from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from core.views import media_serve

handler404 = 'lazer.views.404'
handler500 = 'lazer.views.500'

urlpatterns = [
    path('system/', admin.site.urls),
    # MEDIA FORÇADO (produção)
    path('media/<path:path>/', media_serve),

    path('', include('core.urls')),
]


