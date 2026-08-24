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
    AtualizarEtapaProducaoView,
    FinanceiroInnerView,
    GuiasProducaoView,
    MinhaProducaoView,
    OrcamentosInnerView,
    OrdemProducaoDetalheView,
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
    path('producao/', MinhaProducaoView.as_view(), name='minha_producao'),
    path('producao/guias/', GuiasProducaoView.as_view(), name='guias_producao'),
    path('producao/produtos/', ProdutosProducaoView.as_view(), name='produtos_producao'),
    path('producao/ordens/', OrdensProducaoView.as_view(), name='ordens_producao'),
    path(
        'producao/ordens/<int:pk>/',
        OrdemProducaoDetalheView.as_view(),
        name='producao_ordem_detalhe',
    ),
    path(
        'producao/ordens/<int:pk>/etapas/<int:etapa_id>/',
        AtualizarEtapaProducaoView.as_view(),
        name='atualizar_etapa_producao',
    ),

    # ---------------- acesso ----------------
    path('login/inner/', LoginInternoView.as_view(), name='login_inner'),
    path('logout/inner/', LogoutInnerView.as_view(), name='logout_inner'),

    # ---------------- demais telas ----------------
    path('vendas/inner/', VendasView.as_view(), name='vendas_inner'),
    path('pedidos/inner/', PedidosView.as_view(), name='pedidos_inner'),
    path('manutencoes/inner/', ManutencaoInnerView.as_view(), name='manutencao_inner'),
]
