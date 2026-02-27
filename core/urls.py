from django.urls import path
from .views import (HomeView, BrinquedoInfoView, CategoriasInfoView, BrinquedosView, webhook_mercadopago,
                    RegistrarView, LoginUsuarioView, LogoutUsuarioView, EventosView,
                    ProjetosView, ClientePerfilView, ComboInfoView, PromocaoInfoView,
                    BrinquedoAdmin, NovaCategoria, NovaTag, ComboListView, ComboCreateView,
                    ComboUpdateView, ComboDeleteView, CupomAdminView, ProjetoAdminView, EstabelecimentoInfoView,
                    EstabelecimentosListView, ManutencaoView, PromocaoAdminView, PromocaoDeleteView,
                    adicionar_ao_carrinho, CarrinhoView, aplicar_cupom, remover_item_carrinho,
                    limpar_carrinho, cancelar_manutencao, alterar_quantidade_item, gerar_pix, verificar_pagamento,
                    PaymentView, MeusPedidosView, criar_pedido_pix, PaymentFinallyView, processar_cartao,
                    EventoAdminView, BannerAdminView, BannerDeleteView, AdminLoginView, AcessoNegadoView,
                    DashboardAdminView, UserAdminView, ManutencaoAdminView, RelatorioVendasView, PedidoAdminView,
                    redirecionar_loja, redirecionar_categoria_brinquedos, redirecionar_categoria_aventura, redirecionar_lancamentos,
                    redirecionar_showroom, redirecionar_contato, EstatisticasGeraisView, ReposicaoView, ReposicaoDetalheView, filtrar_pecas_ajax
                    )


urlpatterns = [

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

    path('meus-pedidos/', MeusPedidosView.as_view(), name='meus_pedidos'),

    path('pedido/pix/criar/', criar_pedido_pix, name='criar_pedido_pix'),
    path(
        'pedido/<int:pedido_id>/endereco/',
        PaymentFinallyView.as_view(),
        name='payment_finally'
    ),

    path("ajax/filtrar-pecas/", filtrar_pecas_ajax, name="filtrar_pecas_ajax"),
    path("api/webhook-mp/", webhook_mercadopago, name="webhook_mp"),
    path("verificar-pagamento/", verificar_pagamento, name="verificar_pagamento"),

    path('processar_cartao/', processar_cartao, name='processar_cartao'),

    path('perfil/', ClientePerfilView.as_view(), name='perfil'),
    path("login/", LoginUsuarioView.as_view(), name="login"),
    path("logout/", LogoutUsuarioView.as_view(), name="logout"),
    path("registrar/", RegistrarView.as_view(), name="registrar"),

    path('acesso-negado/', AcessoNegadoView.as_view(), name='acesso_negado'),
]
