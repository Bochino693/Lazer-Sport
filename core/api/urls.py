# core/api/urls.py
#
# Prefixo /api/v1/ separado das rotas do site. Assim o app tem um
# contrato estável: quando você mexer nos templates, a API não quebra.
#
# Já está ativado em lazer/urls.py com:
#     path("api/v1/", include("core.api.urls")),

from django.urls import path

from .auth_views import LoginAPI, LogoutAPI, PerfilAPI, RegistroAPI
from .views import (
    BrinquedoDetalheAPI,
    BrinquedoListAPI,
    CategoriaListAPI,
    PecaDetalheAPI,
    PecaListAPI,
)

app_name = "api"

urlpatterns = [
    # ---------- Autenticação (app) ----------
    path("auth/login/", LoginAPI.as_view(), name="login"),
    path("auth/registro/", RegistroAPI.as_view(), name="registro"),
    path("auth/logout/", LogoutAPI.as_view(), name="logout"),
    path("auth/perfil/", PerfilAPI.as_view(), name="perfil"),

    # ---------- Catálogo (público) ----------
    path("categorias/", CategoriaListAPI.as_view(), name="categorias"),
    path("brinquedos/", BrinquedoListAPI.as_view(), name="brinquedos"),
    path(
        "brinquedos/<int:pk>/",
        BrinquedoDetalheAPI.as_view(),
        name="brinquedo_detalhe",
    ),
    path("pecas/", PecaListAPI.as_view(), name="pecas"),
    path("pecas/<int:pk>/", PecaDetalheAPI.as_view(), name="peca_detalhe"),
]