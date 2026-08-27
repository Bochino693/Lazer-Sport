from django.urls import path

from core.views import (
    BannerAdminView,
    BannerDeleteView,
    BrinquedoAdmin,
    ClienteAdminView,
    ComboAdminView,
    CupomAdminView,
    DashboardAdminView,
    EventoAdminView,
    EstatisticasGeraisView,
    NovaCategoria,
    NovaTag,
    ProjetoAdminView,
    PromocaoAdminView,
    UserAdminView,
)
from core.views_gestao_produtos import EngajamentoAdminView, PecaAdminView

from .permissoes import CRIACAO, GESTAO, VENDAS

from .views import (
    DashboardEstoqueView,
    EstoqueInnerView,
    HomeInnerView,
    LoginInternoView,
    LogoutInnerView,
    MinhaContaView,
    ManutencaoInnerView,
    MateriaisInnerView,
    MovimentacoesInnerView,
    PedidosView,
    VendasView,
)
from .views_app import manifesto, service_worker
from .views_acessos import AvaliacaoSetoresInnerView, UsuariosEquipeInnerView
from .views_clientes import ClientesInnerView, ConsultaCepInnerView
from .views_gestao import (
    AtualizarEtapaProducaoView,
    BuscaClientesOrcamentoView,
    BuscaItensOrcamentoView,
    FinanceiroInnerView,
    GuiasProducaoView,
    MinhaProducaoView,
    OrcamentosInnerView,
    OrcamentoPreviaInnerView,
    OrdemProducaoDetalheView,
    OrdensProducaoView,
    ProdutosProducaoView,
)
from .views_site import LinkSitePublicoView


def por_funcoes(view_class, *funcoes, somente_super=False):
    """Especializa as views reaproveitadas sem duplicar seus CRUDs."""
    protegida = type(
        f"{view_class.__name__}Interna",
        (view_class,),
        {
            "funcoes_necessarias": funcoes,
            "superusuario_necessario": somente_super,
            "__module__": __name__,
        },
    )
    return protegida.as_view()

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

    # ---------------- catálogo e presença digital ----------------
    # Os CRUDs maduros do antigo /adm são reaproveitados, mas agora vivem
    # no mesmo aplicativo e obedecem à função Criação e site.
    path('site/brinquedos/', por_funcoes(BrinquedoAdmin, CRIACAO), name='brinquedos_admin'),
    path('site/categorias/nova/', por_funcoes(NovaCategoria, CRIACAO), name='categoria_new'),
    path('site/tags/nova/', por_funcoes(NovaTag, CRIACAO), name='tag_new'),
    path('site/combos/', por_funcoes(ComboAdminView, CRIACAO), name='combos_admin'),
    path('site/promocoes/', por_funcoes(PromocaoAdminView, CRIACAO), name='promocoes_admin'),
    path('site/eventos/', por_funcoes(EventoAdminView, CRIACAO), name='eventos_admin'),
    path('site/projetos/', por_funcoes(ProjetoAdminView, CRIACAO), name='projetos_admin'),
    path('site/cupons/', por_funcoes(CupomAdminView, CRIACAO, GESTAO), name='cupons_admin'),
    path('site/pecas/', por_funcoes(PecaAdminView, CRIACAO), name='pecas_admin'),
    path('site/banners/', por_funcoes(BannerAdminView, CRIACAO), name='banner_adm'),
    path(
        'site/banners/excluir/<int:pk>/',
        por_funcoes(BannerDeleteView, CRIACAO),
        name='banner_delete',
    ),
    path('site/engajamento/', por_funcoes(EngajamentoAdminView, CRIACAO, GESTAO), name='engajamento_admin'),
    path('site/indicadores/', por_funcoes(DashboardAdminView, CRIACAO, GESTAO), name='dashboards'),
    path('site/estatisticas/', por_funcoes(EstatisticasGeraisView, CRIACAO, GESTAO), name='estatisticas_gerais'),

    # Gestão de clientes públicos e contas fica visível ao superusuário;
    # os clientes comerciais do dia a dia continuam na tela Clientes.
    path('site/clientes-mapa/', por_funcoes(ClienteAdminView, VENDAS, GESTAO), name='clientes_admin'),
    path(
        'site/contas-clientes/',
        por_funcoes(UserAdminView, somente_super=True),
        name='clients',
    ),

    # Nomes usados pelos templates herdados. O destino sai do subdomínio
    # interno, sem misturar a sessão visual do aplicativo com a vitrine.
    path('abrir-site/', LinkSitePublicoView.as_view(), name='home'),
    path('abrir-site/combo/<int:pk>/', LinkSitePublicoView.as_view(), {'tipo': 'combo'}, name='combo'),

    # ---------------- aplicativo instalável ----------------
    # Os dois respondem na raiz do subdomínio; ver views_app.py.
    path('manifest.webmanifest', manifesto, name='manifesto_interno'),
    path('sw.js', service_worker, name='service_worker_interno'),

    # ---------------- clientes ----------------
    path('clientes/', ClientesInnerView.as_view(), name='clientes_inner'),
    path(
        'clientes/consultar-cep/',
        ConsultaCepInnerView.as_view(),
        name='consultar_cep_inner',
    ),

    # ---------------- orçamentos ----------------
    path('orcamentos/', OrcamentosInnerView.as_view(), name='orcamentos_inner'),
    path(
        'orcamentos/<int:pk>/previa/',
        OrcamentoPreviaInnerView.as_view(),
        name='orcamento_previa_inner',
    ),
    path(
        'orcamentos/itens/buscar/',
        BuscaItensOrcamentoView.as_view(),
        name='buscar_itens_orcamento',
    ),
    path(
        'orcamentos/clientes/buscar/',
        BuscaClientesOrcamentoView.as_view(),
        name='buscar_clientes_orcamento',
    ),

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
    path('minha-conta/', MinhaContaView.as_view(), name='minha_conta_inner'),
    path('equipe/', UsuariosEquipeInnerView.as_view(), name='usuarios_equipe'),
    path(
        'equipe/avaliacoes/',
        AvaliacaoSetoresInnerView.as_view(),
        name='avaliacao_setores',
    ),

    # ---------------- demais telas ----------------
    path('vendas/inner/', VendasView.as_view(), name='vendas_inner'),
    path('pedidos/inner/', PedidosView.as_view(), name='pedidos_inner'),
    path('manutencoes/inner/', ManutencaoInnerView.as_view(), name='manutencao_inner'),
]
