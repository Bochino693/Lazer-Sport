# core/api/urls.py
#
# Prefixo /api/v1/ separado das rotas do site. Assim o app tem um
# contrato estável: quando você mexer nos templates, a API não quebra.
#
# Pra ativar, adicione UMA linha em lazer/urls.py:
#
#     path("api/v1/", include("core.api.urls")),
#
# (o include já está importado lá)

from django.urls import path

from .views import (
    BrinquedoDetalheAPI,
    BrinquedoListAPI,
    CategoriaListAPI,
    PecaDetalheAPI,
    PecaListAPI,
)

app_name = "api"

urlpatterns = [
    path(
        "categorias/",
        CategoriaListAPI.as_view(),
        name="categorias",
    ),
    path(
        "brinquedos/",
        BrinquedoListAPI.as_view(),
        name="brinquedos",
    ),
    path(
        "brinquedos/<int:pk>/",
        BrinquedoDetalheAPI.as_view(),
        name="brinquedo_detalhe",
    ),
    path(
        "pecas/",
        PecaListAPI.as_view(),
        name="pecas",
    ),
    path(
        "pecas/<int:pk>/",
        PecaDetalheAPI.as_view(),
        name="peca_detalhe",
    ),
]