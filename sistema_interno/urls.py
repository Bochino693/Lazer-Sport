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
    LembrarClienteView,
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
from .views_avisos import EstadoAvisosView, InscricaoPushView
from .views_avisos_app import AvisosDoAplicativoView
from .views_acessos import AvaliacaoSetoresInnerView, UsuariosEquipeInnerView
from .views_etiquetas import EtiquetasInnerView
from .views_clientes import (
    ClientesInnerView,
    ConsultaCepInnerView,
    DossieClienteView,
)
from .views_campanhas import (
    AcionarWhatsAppCampanhaView,
    CampanhaDetalheView,
    CampanhasInnerView,
    CriarCampanhaView,
    OfertasDisponiveisView,
    PrepararCampanhaView,
)
from .views_gestao import (
    AtualizarEtapaProducaoView,
    BuscaClientesOrcamentoView,
    BuscaItensOrcamentoView,
    BuscaItensOrdemServicoView,
    EstadoOrcamentosView,
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
from .views_ordens_servico import (
    OrdemServicoPreviaInnerView,
    OrdensServicoInnerView,
)


handler404 = "sistema_interno.resiliencia.pagina_interna_nao_encontrada"
handler500 = "sistema_interno.resiliencia.erro_interno"


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
    # O atalho da fila de urgências: lembrar o cliente sem sair da tela.
    path(
        'orcamentos/<int:pk>/lembrar/',
        LembrarClienteView.as_view(),
        name='lembrar_cliente',
    ),

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
    path('site/campanhas/', CampanhasInnerView.as_view(), name='campanhas_inner'),
    path('site/campanhas/ofertas/', OfertasDisponiveisView.as_view(), name='campanha_ofertas'),
    path('site/campanhas/preparar/', PrepararCampanhaView.as_view(), name='campanha_preparar'),
    path('site/campanhas/criar/', CriarCampanhaView.as_view(), name='campanha_criar'),
    path(
        'site/campanhas/<uuid:token>/',
        CampanhaDetalheView.as_view(),
        name='campanha_detalhe',
    ),
    path(
        'site/campanhas/<uuid:token>/whatsapp/<uuid:entrega_token>/',
        AcionarWhatsAppCampanhaView.as_view(),
        name='campanha_whatsapp',
    ),
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
    path('abrir-site/loja/', LinkSitePublicoView.as_view(), {'tipo': 'loja'}, name='abrir_loja'),
    path('abrir-site/combo/<int:pk>/', LinkSitePublicoView.as_view(), {'tipo': 'combo'}, name='combo'),

    # ---------------- aplicativo instalável ----------------
    # Os dois respondem na raiz do subdomínio; ver views_app.py.
    path('manifest.webmanifest', manifesto, name='manifesto_interno'),
    path('sw.js', service_worker, name='service_worker_interno'),

    # ---------------- clientes ----------------
    path('clientes/', ClientesInnerView.as_view(), name='clientes_inner'),
    # O histórico do cliente é buscado quando alguém abre a ficha, e não
    # junto da lista: carregar orçamentos e O.S. de todos seria pagar por
    # dezenas de consultas que ninguém vai olhar.
    path(
        'clientes/<int:pk>/dossie/',
        DossieClienteView.as_view(),
        name='dossie_cliente',
    ),
    path(
        'clientes/consultar-cep/',
        ConsultaCepInnerView.as_view(),
        name='consultar_cep_inner',
    ),

    # ---------------- expedição ----------------
    # Etiqueta é papel: a tela monta, manda para a impressora e acabou.
    # Nada é gravado. Ver `views_etiquetas.py`.
    path('etiquetas/', EtiquetasInnerView.as_view(), name='etiquetas_inner'),

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
    # A mesma busca, para quem monta a O.S. sem ter acesso a propostas.
    path(
        'ordens-servico/itens/buscar/',
        BuscaItensOrdemServicoView.as_view(),
        name='buscar_itens_ordem_servico',
    ),
    path(
        'orcamentos/clientes/buscar/',
        BuscaClientesOrcamentoView.as_view(),
        name='buscar_clientes_orcamento',
    ),
    # A situação de cada proposta, para a lista acompanhar a resposta do
    # cliente sem ninguém recarregar a tela.
    path(
        'orcamentos/estados/',
        EstadoOrcamentosView.as_view(),
        name='estados_orcamentos',
    ),

    # ---------------- ordens de serviço ----------------
    path(
        'ordens-servico/',
        OrdensServicoInnerView.as_view(),
        name='ordens_servico_inner',
    ),
    path(
        'ordens-servico/<int:pk>/previa/',
        OrdemServicoPreviaInnerView.as_view(),
        name='ordem_servico_previa_inner',
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

    # ---------------- avisos ao vivo ----------------
    # As bolinhas do menu e a central se atualizam sozinhas por aqui: o
    # painel fica aberto o dia inteiro, e aviso que só aparece depois de
    # relogar chega tarde demais.
    path('avisos/estado/', EstadoAvisosView.as_view(), name='avisos_estado'),
    # O aparelho pede (ou desiste de) receber aviso quando o painel está
    # fechado -- é o único caminho até quem está na estrada.
    path('avisos/aparelho/', InscricaoPushView.as_view(), name='avisos_aparelho'),

    # ---------------- notificações do aplicativo (cliente) ----------------
    # Outro público, outra tela: aqui a LOJA fala com quem baixou o
    # aplicativo. Ver `avisos_app.py` para o porquê de as duas listas de
    # aparelhos serem separadas.
    path('aplicativo/avisos/', AvisosDoAplicativoView.as_view(), name='avisos_app'),

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
