from django.urls import path, include
from .views import (HomeInnerView, EstoqueInnerView,
                    LoginInternoView, LogoutInnerView,
                    VendasView, PedidosView, ManutencaoInnerView)

urlpatterns = [

    path('', HomeInnerView.as_view(), name='home_inner'),
    path('stock/', EstoqueInnerView.as_view(), name='stock'),

    path('login/inner/', LoginInternoView.as_view(), name='login_inner'),
    path('logout/inner/', LogoutInnerView.as_view(), name='logout_inner'),

    path('vendas/inner/', VendasView.as_view(), name='vendas_inner'),
    path('pedidos/inner/', PedidosView.as_view(), name='pedidos_inner'),
    path('manutencoes/inner/', ManutencaoInnerView.as_view(), name='manutencao_inner'),

]
