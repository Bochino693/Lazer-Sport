from django.urls import path, re_path
from django.contrib.sitemaps.views import sitemap
from .sitemaps import PaginasEstaticasSitemap, BrinquedosSitemap, CategoriasSitemap
from .views import (HomeView, BrinquedoInfoView, CategoriasInfoView, BrinquedosView, webhook_mercadopago,
                    RegistrarView, LoginUsuarioView, LogoutUsuarioView, EventosView, verificar_pagamento,
                    ProjetosView, ClientePerfilView, ComboInfoView, PromocaoInfoView, calcular_frete, salvar_cpf_carrinho,
                    BrinquedoAdmin, NovaCategoria, NovaTag, ComboListView, ComboCreateView, PedidosParaImpressaoAPI,
                    ComboUpdateView, ComboDeleteView, CupomAdminView, ProjetoAdminView, EstabelecimentoInfoView,
                    EstabelecimentosListView, ManutencaoView, PromocaoAdminView, PromocaoDeleteView,
                    adicionar_ao_carrinho, CarrinhoView, aplicar_cupom, remover_item_carrinho, MarcarPedidoImpressoAPI,
                    limpar_carrinho, cancelar_manutencao, alterar_quantidade_item, gerar_pix, atualizar_tipo_envio,
                    PaymentView, MeusPedidosView, criar_pedido_pix, processar_cartao, EventoAdminView, BannerAdminView, BannerDeleteView, AdminLoginView, AcessoNegadoView,
                    DashboardAdminView, UserAdminView, ManutencaoAdminView, RelatorioVendasView, PedidoAdminView,
                    redirecionar_loja, redirecionar_categoria_brinquedos, redirecionar_categoria_aventura, redirecionar_lancamentos,
                    redirecionar_showroom, redirecionar_contato, EstatisticasGeraisView, ReposicaoView, ReposicaoDetalheView,
                    robots_txt
                    )

sitemaps = {
    "estaticas": PaginasEstaticasSitemap,
    "brinquedos": BrinquedosSitemap,
    "categorias": CategoriasSitemap,
}


urlpatterns = [

    path('robots.txt', robots_txt, name='robots_txt'),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='sitemap'),

    path('', HomeView.as_view(), name='home'),
    path('loja/', redirecionar_loja),
    path('lancamentos/', redirecionar_lancamentos),
    path('nosso-showroom/', redirecionar_showroom),
    path('contato/', redirecionar_contato),
    path('categoria-produto/brinquedos/', redirecionar_categoria_brinquedos),
    path(
        'categoria-produto/aventura/',
        redirecionar_categoria_aventura
    ),

    # ------------------------------------------------------------------
    # URLs antigas da loja WordPress/WooCommerce que o Google ainda tem
    # indexadas (ex: /categoria-produto/area-baby/, /loja/brinquedos/la-bamba/).
    # Não existe view nenhuma pra esses caminhos exatos -- sem essas rotas
    # coringa, essas URLs voltam erro pro Googlebot, o que faz o Google
    # manter o snapshot antigo (quebrado) no índice por mais tempo em vez
    # de atualizar. Redireciona (301) pro catálogo atual, preservando o
    # crawl budget e passando o valor de SEO acumulado pra página certa.
    # Fica DEPOIS das rotas específicas de categoria-produto acima, senão
    # essas específicas nunca seriam alcançadas.
    path('categoria-produto/<path:resto>', redirecionar_loja),
    path('loja/<path:resto>', redirecionar_loja),
    path('fabricante-de-brinquedo/<path:resto>', redirecionar_loja),

    path('brinquedos/', BrinquedosView.as_view(), name='brinquedos'),
    path("brinquedo/<int:id>/", BrinquedoInfoView.as_view(), name="brinquedo_detalhe"),
    path("categoria/<int:pk>/", CategoriasInfoView.as_view(), name="categoria_detalhe"),
    path("combo/<int:pk>", ComboInfoView.as_view(), name='combo'),
    path("promocao/<int:pk>", PromocaoInfoView.as_view(), name='promocao'),
    path("estabelecimentos/<int:pk>/", EstabelecimentoInfoView.as_view(), name='estabelecimento_brinquedo'),

    path("estabelecimentos/", EstabelecimentosListView.as_view(), name="estabelecimentos"),

    path('adm/login/', AdminLoginView.as_view(), name='admin_login'),

    path(
        'manutencoes/',
        ManutencaoView.as_view(),
        name='manutencoes'
    ),
    path("manutencoes/cancelar/", cancelar_manutencao, name="cancelar_manutencao"),

    path(
        "salvar-cpf-carrinho/",
        salvar_cpf_carrinho,
        name="salvar_cpf_carrinho"
    ),

    path(
        'carrinho/',
        CarrinhoView.as_view(),
        name='carrinho'
    ),

    path(
        "carrinho/alterar-quantidade/",
        alterar_quantidade_item,
        name="alterar_quantidade_item"
    ),

    path(
        'carrinho/adicionar/<str:tipo>/<int:object_id>/',
        adicionar_ao_carrinho,
        name='adicionar_ao_carrinho'
    ),

    path('carrinho/remover-item/', remover_item_carrinho, name='remover_item_carrinho'),
    path('carrinho/limpar/', limpar_carrinho, name='limpar_carrinho'),

    path('calcular/frete/', calcular_frete, name='calcular_frete'),

    path('pecas-reposicao/', ReposicaoView.as_view(), name='pecas_reposicao'),
    path('pecas/<int:pk>/', ReposicaoDetalheView.as_view(), name='reposicao_detalhe'),

    path('carrinho/aplicar-cupom/', aplicar_cupom, name='aplicar_cupom'),


    path("eventos/", EventosView.as_view(), name='eventos'),
    path("projetos/", ProjetosView.as_view(), name='projetos'),

    path('adm/brinquedos/', BrinquedoAdmin.as_view(), name='brinquedos_admin'),
    path('categoria/admin/new/', NovaCategoria.as_view(), name='categoria_new'),
    path('tags/admin/new/', NovaTag.as_view(), name='tag_new'),

    path('adm/combos/', ComboListView.as_view(), name='combos_admin'),
    path('adm/combos/novo/', ComboCreateView.as_view(), name='combo_create'),
    path('adm/combos/editar/<int:pk>/', ComboUpdateView.as_view(), name='combo_update'),
    path('adm/combos/excluir/<int:pk>/', ComboDeleteView.as_view(), name='combo_delete'),

    path('adm/estatisticas/', EstatisticasGeraisView.as_view(), name='estatisticas_gerais'),


    path('adm/banners/', BannerAdminView.as_view(), name='banner_adm'),
    path('adm/banners/excluir/<int:pk>/', BannerDeleteView.as_view(), name='banner_delete'),
    path('adm/pedidos/', PedidoAdminView.as_view(), name='pedidos_adm'),

    path("adm/promocoes/", PromocaoAdminView.as_view(), name="promocoes_admin"),
    path("adm/promocoes/<int:pk>/delete/", PromocaoDeleteView.as_view(), name='promocao_delete'),

    path("adm/dashboards/", DashboardAdminView.as_view(), name='dashboards'),
    path("adm/clients/", UserAdminView.as_view(), name='clients'),
    path("adm/manutencoes/", ManutencaoAdminView.as_view(), name='manutencoes_adm'),
    path('adm/relatorios-vendas/', RelatorioVendasView.as_view(), name='relatorio_vendas'),

    path("adm/eventos/", EventoAdminView.as_view(), name="eventos_admin"),
    path("adm/cupons/", CupomAdminView.as_view(), name="cupons_admin"),

    path("adm/projetos/", ProjetoAdminView.as_view(), name='projetos_admin'),

    path(
        'pagamento/<int:carrinho_id>/',
        PaymentView.as_view(),
        name='pagamento'
    ),

    path("api/gerar-pix/", gerar_pix, name="gerar_pix"),
    path("verificar-pagamento/", verificar_pagamento, name="verificar_pagamento"),

    path('meus-pedidos/', MeusPedidosView.as_view(), name='meus_pedidos'),

    path('pedido/pix/criar/', criar_pedido_pix, name='criar_pedido_pix'),


    path("api/webhook-mp/", webhook_mercadopago, name="webhook_mp"),

    path('processar_cartao/', processar_cartao, name='processar_cartao'),

    path('perfil/', ClientePerfilView.as_view(), name='perfil'),
    path("login/", LoginUsuarioView.as_view(), name="login"),
    path("logout/", LogoutUsuarioView.as_view(), name="logout"),
    path("registrar/", RegistrarView.as_view(), name="registrar"),

    path('acesso-negado/', AcessoNegadoView.as_view(), name='acesso_negado'),

    path('carrinho/<int:carrinho_id>/tipo-envio/', atualizar_tipo_envio, name='atualizar_tipo_envio'),

# Rota de Login que você já tem
    path('adm/login/', AdminLoginView.as_view(), name='admin_login'),



    #API V1

    path(
        "api/v1/pedidos-impressao/",
        PedidosParaImpressaoAPI.as_view(),
        name="api_pedidos_impressao"
    ),

    path(
        "api/v1/pedido-impresso/<int:pedido_id>/",
        MarcarPedidoImpressoAPI.as_view()
    ),

    path('produto-tag/<path:resto>', redirecionar_loja),

    # ------------------------------------------------------------------
    # PEGA-TUDO — fica por ÚLTIMO de propósito (Django resolve rotas de
    # cima pra baixo; tudo que já tem rota própria acima continua
    # funcionando normal). Cobre qualquer URL da loja WooCommerce antiga
    # que a gente ainda não mapeou (achamos /loja/, /categoria-produto/,
    # /fabricante-de-brinquedo/ e /produto-tag/ até agora, mas o Search
    # Console mostrou 635 URLs 404 -- provavelmente tem mais padrões
    # escondidos aí). Em vez de ir caçando prefixo por prefixo toda vez
    # que aparecer um novo no relatório, qualquer coisa sem rota vira
    # redirect 301 pro catálogo, em vez de 404.
    re_path(r'^.*$', redirecionar_loja),

]