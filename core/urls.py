from django.urls import path
from .views import (HomeView, BrinquedoInfoView, CategoriasInfoView, BrinquedosView,
                    RegistrarView, LoginUsuarioView, LogoutUsuarioView, EventosView,
                    ProjetosView, ClientePerfilView, ComboInfoView, PromocaoInfoView,
                    BrinquedoAdmin, NovaCategoria, NovaTag, ComboListView
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


    path("eventos/", EventosView.as_view(), name='eventos'),
    path("projetos/", ProjetosView.as_view(), name='projetos'),


    path('adm/brinquedos/', BrinquedoAdmin.as_view(), name='brinquedos_admin'),
    path('categoria/admin/new/', NovaCategoria.as_view(), name='categoria_new'),
    path('tags/admin/new/', NovaTag.as_view(), name='tag_new'),

    path("adm/combos/", ComboListView.as_view(), name="combos_admin"),


    path('perfil/', ClientePerfilView.as_view(), name='perfil'),
    path("login/", LoginUsuarioView.as_view(), name="login"),
    path("logout/", LogoutUsuarioView.as_view(), name="logout"),
    path("registrar/", RegistrarView.as_view(), name="registrar"),
]

