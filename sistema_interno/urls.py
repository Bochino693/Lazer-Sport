from django.contrib import admin
from django.urls import path, include
from .views import HomeInnerView, EstoqueInnerView

urlpatterns = [

    path('', HomeInnerView.as_view(), name='home_inner'),
    path('relatorios/stock/', EstoqueInnerView.as_view(), name='relatorio_estoque')

]
