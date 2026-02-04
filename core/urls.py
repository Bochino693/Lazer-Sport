from django.urls import path
from .views import (HomeView, BrinquedoInfoView, CategoriasInfoView, BrinquedosView,
                    RegistrarView, LoginUsuarioView, LogoutUsuarioView, EventosView,
                    ProjetosView, ClientePerfilView, ComboInfoView, PromocaoInfoView,
                    BrinquedoAdmin, NovaCategoria, NovaTag, ComboListView, ComboCreateView,
                    ComboUpdateView, ComboDeleteView, PromocaoListView, PromocaoCreateView,
                    CupomAdminView, PromocaoDeleteView, PromocaoUpdateView, ProjetoAdminView,
                    EstabelecimentoInfoView, EstabelecimentosListView, ManutencaoView, adicionar_ao_carrinho,
                    carrinho_view, aplicar_cupom,  remover_item_carrinho, limpar_carrinho, cancelar_manutencao,
                    PaymentView, MeusPedidosView, criar_pedido_pix, PaymentFinallyView, processar_cartao,
                    EventoAdminView, BannerAdminView, BannerDeleteView, AdminLoginView, AcessoNegadoView,
                    DashboardAdminView, UserAdminView

                    )   # importa views do mesmo app
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', HomeView.as_view(), name='home'),


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
        carrinho_view,
        name='carrinho'
    ),


    path(
        'carrinho/adicionar/<str:tipo>/<int:object_id>/',
        adicionar_ao_carrinho,
        name='adicionar_ao_carrinho'
    ),

    path('carrinho/remover-item/', remover_item_carrinho, name='remover_item_carrinho'),
    path('carrinho/limpar/', limpar_carrinho, name='limpar_carrinho'),

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

    path('adm/banners/', BannerAdminView.as_view(), name='banner_adm'),
    path('adm/banners/excluir/<int:pk>/', BannerDeleteView.as_view(), name='banner_delete'),

    path("adm/promocoes/", PromocaoListView.as_view(), name="promocoes_admin"),
    path("adm/promocoes/nova/", PromocaoCreateView.as_view(), name="promocao_create"),
    path("adm/promocoes/<int:pk>/editar/", PromocaoUpdateView.as_view(), name="promocao_update"),
    path("adm/promocoes/<int:pk>/excluir/", PromocaoDeleteView.as_view(), name="promocao_delete"),

    path("adm/dashboards/", DashboardAdminView.as_view(), name='dashboards'),
    path("adm/clients/", UserAdminView.as_view(), name='clients'),


    path("adm/eventos/", EventoAdminView.as_view(), name="eventos_admin"),
    path("adm/cupons/", CupomAdminView.as_view(), name="cupons_admin"),

    path("adm/projetos/", ProjetoAdminView.as_view(), name='projetos_admin'),

    path(
        'pagamento/<int:carrinho_id>/',
        PaymentView.as_view(),
        name='pagamento'
    ),

    path('meus-pedidos/', MeusPedidosView.as_view(), name='meus_pedidos'),

    path('pedido/pix/criar/', criar_pedido_pix, name='criar_pedido_pix'),
    path(
        'pedido/<int:pedido_id>/endereco/',
        PaymentFinallyView.as_view(),
        name='payment_finally'
    ),

    path('processar_cartao/', processar_cartao, name='processar_cartao'),

    path('perfil/', ClientePerfilView.as_view(), name='perfil'),
    path("login/", LoginUsuarioView.as_view(), name="login"),
    path("logout/", LogoutUsuarioView.as_view(), name="logout"),
    path("registrar/", RegistrarView.as_view(), name="registrar"),


    path('acesso-negado/', AcessoNegadoView.as_view(), name='acesso_negado'),
]

