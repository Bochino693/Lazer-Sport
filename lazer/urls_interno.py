from django.urls import path, include

urlpatterns = [
    path('', include('sistema_interno.urls')),
    path('', include('core.urls_admin')),  # banners, manutenções, etc
]
