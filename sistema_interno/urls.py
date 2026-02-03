from django.contrib import admin
from django.urls import path, include
from .views import HomeInnerView, EstoqueInnerView, LoginInternoView

urlpatterns = [

    path('', HomeInnerView.as_view(), name='home_inner'),
    path('stock/', EstoqueInnerView.as_view(), name='stock'),

    path('login/inner/', LoginInternoView.as_view(), name='login_inner'),

]
