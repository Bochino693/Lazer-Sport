from django.contrib.staticfiles.storage import staticfiles_storage
from django.views.generic import RedirectView, TemplateView
from django.urls import path, re_path
from django.contrib.sitemaps.views import sitemap

from .views_favoritos import (
    ListaDesejosView,
    alternar_favorito,
    meus_favoritos,
)
from .views_gestao_produtos import EngajamentoAdminView, PecaAdminView
from .views_app_avisos import service_worker_do_site
from .escudo_jogos import ArmadilhaView, PasseDoJogoView
from .views_app_jogos import manifesto_dos_jogos, service_worker_dos_jogos
from sistema_interno.views_avisos_app import InscricaoDoAplicativoView
from .views_arena import ArenaView
from .views_jogos import (AbriuJogoView, AnuncioJogosView, ArquivoDoEmuladorView, JogoEmuladorView, PartidaJogoView,
                          PortalJogosView, RankingJogosView, SimuladorView)
from .views_painel import painel_ao_vivo
from .views_orcamento import orcamento_publico
from .views_ordem_servico import ordem_servico_publica
from sistema_interno.views_campanhas import CampanhaPublicaDestinoView, CampanhaPublicaView
from .views_redirects import redirecionar_interno
from .sitemaps import (
    PaginasEstaticasSitemap,
    BrinquedosSitemap,
    CategoriasSitemap,
    JogosSitemap,
    PecasSitemap,
    TemasSitemap,
)
from . import indexnow
from .paginas_tema import TEMAS
from .views_tema import pagina_tema
from .views import (
    HomeView,
    BrinquedoInfoView,
    CategoriasInfoView,
    BrinquedosView,
    webhook_mercadopago,
    EventosView,
    verificar_pagamento,
    confirmacoes_pendentes,
    marcar_confirmacao_vista,
    devolver_pedido_ao_carrinho,
    ProjetosView,
    ClientePerfilView,
    ComboInfoView,
    PromocaoInfoView,
    calcular_frete,
    salvar_cpf_carrinho,
    BrinquedoAdmin,
    NovaCategoria,
    NovaTag,
    PedidosParaImpressaoAPI,
    CupomAdminView,
    ProjetoAdminView,
    EstabelecimentoInfoView,
    EstabelecimentosListView,
    ManutencaoView,
    PromocaoAdminView,
    adicionar_ao_carrinho,
    CarrinhoView,
    aplicar_cupom,
    remover_item_carrinho,
    MarcarPedidoImpressoAPI,
    limpar_carrinho,
    cancelar_manutencao,
    alterar_quantidade_item,
    gerar_pix,
    atualizar_tipo_envio,
    PaymentView,
    MeusPedidosView,
    criar_pedido_pix,
    processar_cartao,
    EventoAdminView,
    BannerAdminView,
    BannerDeleteView,
    AcessoNegadoView,
    DashboardAdminView,
    UserAdminView,
    ManutencaoAdminView,
    RelatorioVendasView,
    PedidoAdminView,
    redirecionar_loja,
    redirecionar_endereco_antigo,
    redirecionar_categoria_brinquedos,
    redirecionar_categoria_aventura,
    redirecionar_lancamentos,
    redirecionar_showroom,
    redirecionar_contato,
    EstatisticasGeraisView,
    ReposicaoView,
    ReposicaoDetalheView,
    healthz,
    pronto,
    robots_txt,
    ComboAdminView,
    SearchView,
    LojaView,
    ClienteAdminView,
)
from .views_conta import (
    ContaTransicaoView,
    LoginUsuarioView,
    LogoutUsuarioView,
    RegistrarView,
    DesafioHumanoView,
    CompletarPerfilView,
)

from .api.views import (
    BrinquedoDetalheAPI,
    BrinquedoListAPI,
    CategoriaListAPI,
    PecaDetalheAPI,
    PecaListAPI,

)


sitemaps = {
    "estaticas": PaginasEstaticasSitemap,
    "temas": TemasSitemap,
    "pecas": PecasSitemap,
    "brinquedos": BrinquedosSitemap,
    "categorias": CategoriasSitemap,
    "jogos": JogosSitemap,
}


class PrivacidadeView(TemplateView):
    """A política de privacidade (/privacidade/): o que o site guarda e por quê."""

    template_name = "privacidade.html"


urlpatterns = [
    path("healthz/", healthz, name="healthz"),
    # O painel chama este para acordar processo E banco antes de agir.
    # Ver `core.views.pronto`.
    path("pronto/", pronto, name="pronto"),
    path("robots.txt", robots_txt, name="robots_txt"),
    path("privacidade/", PrivacidadeView.as_view(), name="privacidade"),
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="sitemap"),
    # A chave do IndexNow (core/indexnow.py): /<chave>.txt, só a configurada.
    re_path(r"^(?P<nome>[A-Za-z0-9-]{8,128})\.txt$", indexnow.arquivo_da_chave, name="indexnow_chave"),

    # ---------------- avisos no celular do cliente ----------------
    # O aparelho de quem baixou o aplicativo pede (ou desiste de) receber
    # aviso da loja. A tela que ESCREVE o aviso mora no painel; aqui só
    # entra e sai o endereço de entrega. Ver `sistema_interno/avisos_app.py`.
    path(
        "aplicativo/avisos/aparelho/",
        InscricaoDoAplicativoView.as_view(),
        name="inscricao_avisos_app",
    ),
    # O service worker precisa responder na RAIZ: ele só controla o que
    # está abaixo do caminho em que é servido, e em /static/ não
    # controlaria página nenhuma -- sem isso, notificação não chega.
    path("app-sw.js", service_worker_do_site, name="service_worker_site"),

    path("", HomeView.as_view(), name="home"),
    path("loja/", LojaView.as_view(), name="loja"),
    path("lancamentos/", redirecionar_lancamentos),
    path("nosso-showroom/", redirecionar_showroom),
    path("contato/", redirecionar_contato),
    path("categoria-produto/brinquedos/", redirecionar_categoria_brinquedos),
    path("categoria-produto/aventura/", redirecionar_categoria_aventura),

    # URLs antigas do WordPress/WooCommerce.
    path("categoria-produto/<path:resto>", redirecionar_endereco_antigo),
    path("loja/<path:resto>", redirecionar_endereco_antigo),
    path("fabricante-de-brinquedo/<path:resto>", redirecionar_endereco_antigo),

    path("brinquedos/", BrinquedosView.as_view(), name="brinquedos"),
    # Páginas por tema de busca (core/paginas_tema.py): /boliche/, /fliperama/...
    re_path(r"^(?P<tema>%s)/$" % "|".join(TEMAS), pagina_tema, name="pagina_tema"),
    path(
        "brinquedo/<int:id>/",
        BrinquedoInfoView.as_view(),
        name="brinquedo_detalhe",
    ),
    path(
        "categoria/<int:pk>/",
        CategoriasInfoView.as_view(),
        name="categoria_detalhe",
    ),
    path("combo/<int:pk>", ComboInfoView.as_view(), name="combo"),
    path("promocao/<int:pk>", PromocaoInfoView.as_view(), name="promocao"),
    path(
        "divulgacao/<uuid:token>/",
        CampanhaPublicaView.as_view(),
        name="campanha_publica",
    ),
    path(
        "divulgacao/<uuid:token>/visitar/",
        CampanhaPublicaDestinoView.as_view(),
        name="campanha_publica_destino",
    ),
    path(
        "estabelecimentos/<int:pk>/",
        EstabelecimentoInfoView.as_view(),
        name="estabelecimento_brinquedo",
    ),
    path(
        "estabelecimentos/",
        EstabelecimentosListView.as_view(),
        name="estabelecimentos",
    ),

    path("adm/login/", redirecionar_interno("login_inner"), name="admin_login"),

    path("manutencoes/", ManutencaoView.as_view(), name="manutencoes"),
    path(
        "manutencoes/cancelar/",
        cancelar_manutencao,
        name="cancelar_manutencao",
    ),

    path(
        "salvar-cpf-carrinho/",
        salvar_cpf_carrinho,
        name="salvar_cpf_carrinho",
    ),
    path("carrinho/", CarrinhoView.as_view(), name="carrinho"),
    path(
        "carrinho/alterar-quantidade/",
        alterar_quantidade_item,
        name="alterar_quantidade_item",
    ),
    path(
        "carrinho/adicionar/<str:tipo>/<int:object_id>/",
        adicionar_ao_carrinho,
        name="adicionar_ao_carrinho",
    ),
    path(
        "carrinho/remover-item/",
        remover_item_carrinho,
        name="remover_item_carrinho",
    ),
    path("carrinho/limpar/", limpar_carrinho, name="limpar_carrinho"),
    path("calcular/frete/", calcular_frete, name="calcular_frete"),

    path("pecas-reposicao/", ReposicaoView.as_view(), name="pecas_reposicao"),
    path(
        "pecas/<int:pk>/",
        ReposicaoDetalheView.as_view(),
        name="reposicao_detalhe",
    ),
    path(
        "carrinho/aplicar-cupom/",
        aplicar_cupom,
        name="aplicar_cupom",
    ),

    # Arena e Lazer & Sport Jogos -- no lugar que era de "Nossos
    # Parceiros" no menu. A página de parceiros continua em
    # /estabelecimentos/, com link a partir da arena e da busca.
    path("arena/", ArenaView.as_view(), name="arena"),
    path("api/painel-ao-vivo/", painel_ao_vivo, name="painel_ao_vivo"),
    # O simulador: a área dedicada às prévias dos jogos, um endereço por jogo.
    path("jogos/", PortalJogosView.as_view(), name="jogos"),
    # o app Lazer & Sport Games: instalar na tela de início e abrir sem internet
    path("jogos/sw.js", service_worker_dos_jogos, name="jogos_app_sw"),
    path("jogos/app.webmanifest", manifesto_dos_jogos, name="jogos_app_manifesto"),
    path("jogos/abriu/", AbriuJogoView.as_view(), name="jogos_abriu"),
    # a armadilha dos robôs (escondida na biblioteca, proibida no robots.txt): ver core/escudo_jogos.py
    path("jogos/_acervo/", ArmadilhaView.as_view(), name="jogos_armadilha"),
    path("jogos/anuncio/<int:pk>/", AnuncioJogosView.as_view(), name="anuncio_jogos"),
    # antes de jogos/<slug>/: "partida" e "ranking" não são jogos
    path("jogos/partida/", PartidaJogoView.as_view(), name="jogos_partida"),
    path("jogos/ranking/", RankingJogosView.as_view(), name="jogos_ranking"),
    path("jogos/<slug:slug>/", SimuladorView.as_view(), name="jogo"),
    # jogos de console pelo emulador: a página do quadro e o índice (.cue/.m3u)
    path("jogos/<slug:slug>/emulador/", JogoEmuladorView.as_view(), name="jogo_emulador"),
    # o passe: a prova de trabalho que libera de onde baixar o jogo (core/escudo_jogos.py)
    path("jogos/<slug:slug>/passe/", PasseDoJogoView.as_view(), name="jogo_passe"),
    path("jogos/<slug:slug>/emulador/<path:nome>", ArquivoDoEmuladorView.as_view(), name="jogo_emulador_arquivo"),

    path("eventos/", EventosView.as_view(), name="eventos"),
    path("projetos/", ProjetosView.as_view(), name="projetos"),

    path("adm/brinquedos/", redirecionar_interno("brinquedos_admin"), name="brinquedos_admin"),
    path("categoria/admin/new/", redirecionar_interno("categoria_new"), name="categoria_new"),
    path("tags/admin/new/", redirecionar_interno("tag_new"), name="tag_new"),
    path("adm/combos/", redirecionar_interno("combos_admin"), name="combos_admin"),
    path(
        "adm/estatisticas/",
        redirecionar_interno("estatisticas_gerais"),
        name="estatisticas_gerais",
    ),
    path("adm/banners/", redirecionar_interno("banner_adm"), name="banner_adm"),
    path(
        "adm/banners/excluir/<int:pk>/",
        redirecionar_interno("banner_delete"),
        name="banner_delete",
    ),
    path("adm/pedidos/", redirecionar_interno("pedidos_inner"), name="pedidos_adm"),
    path(
        "adm/promocoes/",
        redirecionar_interno("promocoes_admin"),
        name="promocoes_admin",
    ),
    path("adm/dashboards/", redirecionar_interno("dashboards"), name="dashboards"),
    path("adm/clients/", redirecionar_interno("clients"), name="clients"),
    path(
        "adm/manutencoes/",
        redirecionar_interno("manutencao_inner"),
        name="manutencoes_adm",
    ),
    path(
        "adm/relatorios-vendas/",
        redirecionar_interno("financeiro_inner"),
        name="relatorio_vendas",
    ),
    path("adm/clientes/", redirecionar_interno("clientes_admin"), name="clientes_admin"),
    path("adm/eventos/", redirecionar_interno("eventos_admin"), name="eventos_admin"),
    path("adm/cupons/", redirecionar_interno("cupons_admin"), name="cupons_admin"),
    path("adm/projetos/", redirecionar_interno("projetos_admin"), name="projetos_admin"),
    path("adm/pecas/", redirecionar_interno("pecas_admin"), name="pecas_admin"),
    path(
        "adm/engajamento/",
        redirecionar_interno("engajamento_admin"),
        name="engajamento_admin",
    ),

    path(
        "pagamento/<int:carrinho_id>/",
        PaymentView.as_view(),
        name="pagamento",
    ),
    path("api/gerar-pix/", gerar_pix, name="gerar_pix"),
    path(
        "verificar-pagamento/",
        verificar_pagamento,
        name="verificar_pagamento",
    ),
    path("meus-pedidos/", MeusPedidosView.as_view(), name="meus_pedidos"),
    path("pedido/pix/criar/", criar_pedido_pix, name="criar_pedido_pix"),
    path("pesquisa/", SearchView.as_view(), name="search"),
    path("api/webhook-mp/", webhook_mercadopago, name="webhook_mp"),
    path(
        "api/confirmacoes/",
        confirmacoes_pendentes,
        name="confirmacoes_pendentes",
    ),
    path(
        "api/confirmacoes/vista/",
        marcar_confirmacao_vista,
        name="marcar_confirmacao_vista",
    ),
    path(
        "api/pedido/devolver-carrinho/",
        devolver_pedido_ao_carrinho,
        name="devolver_pedido_carrinho",
    ),
    path("processar_cartao/", processar_cartao, name="processar_cartao"),

    # Conta pública: todas as views vêm de core/views_conta.py.
    path("perfil/", ClientePerfilView.as_view(), name="perfil"),
    path("login/", LoginUsuarioView.as_view(), name="login"),
    path("logout/", LogoutUsuarioView.as_view(), name="logout"),
    path("registrar/", RegistrarView.as_view(), name="registrar"),
    path("registrar/desafio/", DesafioHumanoView.as_view(), name="registrar_desafio"),
    path(
        "completar-perfil/",
        CompletarPerfilView.as_view(),
        name="completar_perfil",
    ),
    path(
        "conta-transicao/",
        ContaTransicaoView.as_view(),
        name="conta_transicao",
    ),

    path("acesso-negado/", AcessoNegadoView.as_view(), name="acesso_negado"),
    path(
        "carrinho/<int:carrinho_id>/tipo-envio/",
        atualizar_tipo_envio,
        name="atualizar_tipo_envio",
    ),

    path(
        "api/v1/pedidos-impressao/",
        PedidosParaImpressaoAPI.as_view(),
        name="api_pedidos_impressao",
    ),
    path(
        "api/v1/pedido-impresso/<int:pedido_id>/",
        MarcarPedidoImpressoAPI.as_view(),
    ),


    #Rotas da Api do app V1
# ---- API v1 (app Android) — SEMPRE antes do catch-all ----
    path("api/v1/categorias/", CategoriaListAPI.as_view(), name="api_categorias"),
    path("api/v1/brinquedos/", BrinquedoListAPI.as_view(), name="api_brinquedos"),
    path("api/v1/brinquedos/<int:pk>/", BrinquedoDetalheAPI.as_view(), name="api_brinquedo"),
    path("api/v1/pecas/", PecaListAPI.as_view(), name="api_pecas"),
    path("api/v1/pecas/<int:pk>/", PecaDetalheAPI.as_view(), name="api_peca"),



    path("produto-tag/<path:resto>", redirecionar_endereco_antigo),

    # ---- Curtidas e lista de desejos ----
    # Funciona sem login: quem não entrou fica preso ao próprio aparelho.
    path(
        "favoritos/alternar/",
        alternar_favorito,
        name="alternar_favorito",
    ),
    path(
        "lista-desejos/",
        ListaDesejosView.as_view(),
        name="lista_desejos",
    ),
    path(
        "favoritos/meus/",
        meus_favoritos,
        name="meus_favoritos",
    ),

    # ---- Orçamento que o cliente abre ----
    # Antes do catch-all, senão o re_path abaixo engole a rota e manda o
    # cliente para a loja. O token é a chave: nada de id sequencial aqui.
    path(
        "orcamento/<str:token>/",
        orcamento_publico,
        name="orcamento_publico",
    ),
    path(
        "ordem-servico/<str:token>/",
        ordem_servico_publica,
        name="ordem_servico_publica",
    ),

    # O ÍCONE DA ABA, ANTES DO CURINGA.
    #
    # /favicon.ico caía no `re_path` abaixo e era redirecionado para a
    # loja -- no site o navegador recebia uma página HTML no lugar de uma
    # imagem, e no subdomínio interno o destino nem existe: 404 em toda
    # abertura do painel, e aba sem ícone. Não é decoração: quem trabalha
    # com o painel e o site abertos ao mesmo tempo acha a aba pelo ícone.
    path(
        "favicon.ico",
        # o .ico com o 16, o 32 e o 48 desenhados um a um (partials/icones_da_aba.html)
        RedirectView.as_view(url=staticfiles_storage.url("images/icone/favicon.ico")),
        name="favicon",
    ),

    # Deve permanecer por último.
    re_path(r"^.*$", redirecionar_loja),








]
