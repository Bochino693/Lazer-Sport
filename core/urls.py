from django.urls import path
from .views import (HomeView, BrinquedoInfoView, CategoriasInfoView, BrinquedosView,
                    RegistrarView, LoginUsuarioView, LogoutUsuarioView, EventosView,
                    ProjetosView, ClientePerfilView, ComboInfoView, PromocaoInfoView,
                    BrinquedoAdmin, NovaCategoria, NovaTag, ComboListView, ComboCreateView,
                    ComboUpdateView, ComboDeleteView, PromocaoListView, PromocaoCreateView,
                    PromocaoDeleteView, PromocaoUpdateView, EventoListView, EventoCreateView,
                    EventoDeleteView, EventoUpdateView, CupomListView, CupomUpdateView, CupomCreateView,
                    CupomDeleteView, ProjetoListView, ProjetoUpdateView, ProjetoCreateView, ProjetoDeleteView

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

    path('adm/combos/', ComboListView.as_view(), name='combos_admin'),
    path('adm/combos/novo/', ComboCreateView.as_view(), name='combo_create'),
    path('adm/combos/editar/<int:pk>/', ComboUpdateView.as_view(), name='combo_update'),
    path('adm/combos/excluir/<int:pk>/', ComboDeleteView.as_view(), name='combo_delete'),


    path("adm/promocoes/", PromocaoListView.as_view(), name="promocoes_admin"),
    path("adm/promocoes/nova/", PromocaoCreateView.as_view(), name="promocao_create"),
    path("adm/promocoes/<int:pk>/editar/", PromocaoUpdateView.as_view(), name="promocao_update"),
    path("adm/promocoes/<int:pk>/excluir/", PromocaoDeleteView.as_view(), name="promocao_delete"),


    path("adm/eventos/", EventoListView.as_view(), name='eventos_admin'),
    path("adm/eventos/novo/", EventoCreateView.as_view(), name='eventos_create'),
    path("adm/eventos/<int:pk>/editar/", EventoUpdateView.as_view(), name='eventos_update'),
    path("adm/eventos/<int:pk>/excluir/", EventoDeleteView.as_view(), name='eventos_delete'),

    path("adm/cupons/", CupomListView.as_view(), name='cupons_admin'),
    path("adm/cupons/novo/", CupomCreateView.as_view(), name='cupons_create'),
    path("adm/cupons/<int:pk>/editar", CupomUpdateView.as_view(), name='cupons_update'),
    path("adm/cupons/<int:pk>/excluir/", CupomDeleteView.as_view(), name='cupons_delete'),

    path("adm/projetos/", ProjetoListView.as_view(), name='projetos_admin'),
    path("projetos/criar/", ProjetoCreateView.as_view(), name="projetos_criar"),
    path('adm/projetos/<int:pk>/editar', ProjetoUpdateView.as_view(), name='projetos_update'),
    path("adm/projetos/<int:pk>/excluir/", ProjetoDeleteView.as_view(), name='projetos_delete'),

    path('perfil/', ClientePerfilView.as_view(), name='perfil'),
    path("login/", LoginUsuarioView.as_view(), name="login"),
    path("logout/", LogoutUsuarioView.as_view(), name="logout"),
    path("registrar/", RegistrarView.as_view(), name="registrar"),
]

