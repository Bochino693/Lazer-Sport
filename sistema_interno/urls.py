from django.urls import path

from .views import (
    DashboardEstoqueView,
    EstoqueInnerView,
    HomeInnerView,
    LoginInternoView,
    LogoutInnerView,
    ManutencaoInnerView,
    MateriaisInnerView,
    MovimentacoesInnerView,
    PedidosView,
    VendasView,
)
from .views_gestao import (
    FinanceiroInnerView,
    OrcamentosInnerView,
    OrdensProducaoView,
    ProdutosProducaoView,
)

urlpatterns = [
    path('', HomeInnerView.as_view(), name='home_inner'),

    # ---------------- estoque de materiais ----------------
    path('stock/', EstoqueInnerView.as_view(), name='stock'),
    path('estoque/', EstoqueInnerView.as_view(), name='estoque_inner'),
    path('estoque/materiais/', MateriaisInnerView.as_view(), name='materiais_inner'),
    path('estoque/movimentacoes/', MovimentacoesInnerView.as_view(), name='movimentacoes_inner'),
    path('estoque/dashboard/', DashboardEstoqueView.as_view(), name='dashboard_estoque'),

    # ---------------- financeiro ----------------
    path('financeiro/', FinanceiroInnerView.as_view(), name='financeiro_inner'),

    # ---------------- orçamentos ----------------
    path('orcamentos/', OrcamentosInnerView.as_view(), name='orcamentos_inner'),

    # ---------------- produção ----------------
    path('producao/produtos/', ProdutosProducaoView.as_view(), name='produtos_producao'),
    path('producao/ordens/', OrdensProducaoView.as_view(), name='ordens_producao'),

    # ---------------- acesso ----------------
    path('login/inner/', LoginInternoView.as_view(), name='login_inner'),
    path('logout/inner/', LogoutInnerView.as_view(), name='logout_inner'),

    # ---------------- demais telas ----------------
    path('vendas/inner/', VendasView.as_view(), name='vendas_inner'),
    path('pedidos/inner/', PedidosView.as_view(), name='pedidos_inner'),
    path('manutencoes/inner/', ManutencaoInnerView.as_view(), name='manutencao_inner'),
]
