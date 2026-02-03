from django.urls import path, include

urlpatterns = [
    path('', include('sistema_interno.urls')),
]
