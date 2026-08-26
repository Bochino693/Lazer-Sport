# core/api/urls.py

from django.urls import path

from .auth_app_views import AppEntrarSocial, AppTokenSocial
from .auth_views import LoginAPI, LogoutAPI, PerfilAPI, RegistroAPI
from .carrinho_views import SincronizarCarrinhoAPI
from .favoritos_views import FavoritoAlternarAPI, FavoritoListaAPI
from .views import (
    BrinquedoDetalheAPI,
    BrinquedoListAPI,
    CategoriaListAPI,
    ComboListAPI,
    EstabelecimentoListAPI,
    EventoListAPI,
    ManutencaoListCreateAPI,
    PecaDetalheAPI,
    PecaListAPI,
    PedidoListAPI,
    PromocaoListAPI,
    StatusAPI,
)

app_name = "api"

urlpatterns = [
    # ---------- Saúde da API ----------
    path("status/", StatusAPI.as_view(), name="status"),

    # ---------- Autenticação ----------
    path("auth/login/", LoginAPI.as_view(), name="login"),
    path("auth/registro/", RegistroAPI.as_view(), name="registro"),
    path("auth/logout/", LogoutAPI.as_view(), name="logout"),
    path("auth/perfil/", PerfilAPI.as_view(), name="perfil"),

    # ---------- Login social do app ----------
    path("auth/app/entrar/", AppEntrarSocial.as_view(), name="app_entrar"),
    path("auth/app/token/", AppTokenSocial.as_view(), name="app_token"),

    # ---------- Catálogo (público) ----------
    path("categorias/", CategoriaListAPI.as_view(), name="categorias"),
    path("brinquedos/", BrinquedoListAPI.as_view(), name="brinquedos"),
    path("brinquedos/<int:pk>/", BrinquedoDetalheAPI.as_view(), name="brinquedo_detalhe"),
    path("pecas/", PecaListAPI.as_view(), name="pecas"),
    path("pecas/<int:pk>/", PecaDetalheAPI.as_view(), name="peca_detalhe"),

    # ---------- Curtidas e lista de desejos (funciona sem login) ----------
    path("favoritos/", FavoritoListaAPI.as_view(), name="favoritos"),
    path(
        "favoritos/alternar/",
        FavoritoAlternarAPI.as_view(),
        name="favoritos_alternar",
    ),

    # ---------- Institucional (público) ----------
    path("estabelecimentos/", EstabelecimentoListAPI.as_view(), name="estabelecimentos"),
    path("eventos/", EventoListAPI.as_view(), name="eventos"),
    path("combos/", ComboListAPI.as_view(), name="combos"),
    path("promocoes/", PromocaoListAPI.as_view(), name="promocoes"),

    # ---------- Área logada ----------
    path("manutencoes/", ManutencaoListCreateAPI.as_view(), name="manutencoes"),
    path("pedidos/", PedidoListAPI.as_view(), name="pedidos"),
    path(
        "carrinho/sincronizar/",
        SincronizarCarrinhoAPI.as_view(),
        name="carrinho_sincronizar",
    ),
]