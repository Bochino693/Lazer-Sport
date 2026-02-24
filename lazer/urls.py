from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from core.views import media_serve

handler404 = 'core.views.erro_404'
handler500 = 'core.views.erro_500'

urlpatterns = [
    path('system/', admin.site.urls),
    # MEDIA FORÇADO (produção)
    path('media/<path:path>/', media_serve),

    path('accounts/', include('allauth.urls')),

]
