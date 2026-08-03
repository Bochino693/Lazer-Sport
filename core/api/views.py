# core/api/views.py
#
# Fatia 1 -- Catálogo (somente leitura).
#
# Duas decisões de performance embutidas aqui, aprendidas com o
# episódio da Vercel:
#
# 1) PAGINAÇÃO DE VERDADE. O site manda o catálogo inteiro e pagina no
#    JavaScript. No app isso seria pior ainda -- o cliente no 4G
#    baixaria tudo pra ver 9 itens. Aqui são 20 por página, servidos
#    sob demanda.
#
# 2) CACHE. O catálogo muda pouco. 10 minutos de cache por página
#    significa que 500 aberturas do app viram poucas queries no
#    Supabase, não 500.
#
# PERMISSÕES: o settings.py tem DEFAULT_PERMISSION_CLASSES = AllowAny
# global. Isso é aceitável pra catálogo (é público mesmo), mas quando
# chegarmos na fatia 2 (login) cada view de usuário PRECISA declarar
# permission_classes = [IsAuthenticated] explicitamente. Não confie no
# default -- ele está aberto.

from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from rest_framework import generics
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny

from core.models import Brinquedos, CategoriasBrinquedos, PecasReposicao

from core.api.serializer import (
    BrinquedoDetalheSerializer,
    BrinquedoListaSerializer,
    CategoriaSerializer,
    PecaSerializer,
)

CACHE_CATALOGO = 60 * 10  # 10 minutos


class PaginacaoPadrao(PageNumberPagination):
    page_size = 20
    page_size_query_param = "tamanho"
    max_page_size = 60


class CategoriaListAPI(generics.ListAPIView):
    serializer_class = CategoriaSerializer
    permission_classes = [AllowAny]
    pagination_class = None  # são poucas, manda todas

    def get_queryset(self):
        return (
            CategoriasBrinquedos.objects
            .filter(ativo=True)
            .only("id", "nome_categoria", "imagem_categoria")
            .order_by("nome_categoria")
        )

    @method_decorator(cache_page(CACHE_CATALOGO))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


class BrinquedoListAPI(generics.ListAPIView):
    """GET /api/v1/brinquedos/?categoria=3&busca=cama&page=2"""

    serializer_class = BrinquedoListaSerializer
    permission_classes = [AllowAny]
    pagination_class = PaginacaoPadrao

    def get_queryset(self):
        qs = (
            Brinquedos.objects
            .filter(ativo=True)
            .only(
                "id",
                "nome_brinquedo",
                "imagem_brinquedo",
                "valor_brinquedo",
                "avaliacao",
                "exibir_na_loja",
            )
            .order_by("nome_brinquedo")
        )

        categoria = self.request.query_params.get("categoria")
        if categoria:
            qs = qs.filter(categorias_brinquedos__id=categoria)

        busca = self.request.query_params.get("busca")
        if busca:
            qs = qs.filter(nome_brinquedo__icontains=busca)

        # distinct() porque o filtro por categoria é M2M e pode duplicar
        return qs.distinct()

    @method_decorator(cache_page(CACHE_CATALOGO))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


class BrinquedoDetalheAPI(generics.RetrieveAPIView):
    """GET /api/v1/brinquedos/42/"""

    serializer_class = BrinquedoDetalheSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return (
            Brinquedos.objects
            .filter(ativo=True)
            .prefetch_related("categorias_brinquedos")
        )

    @method_decorator(cache_page(CACHE_CATALOGO))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


class PecaListAPI(generics.ListAPIView):
    serializer_class = PecaSerializer
    permission_classes = [AllowAny]
    pagination_class = PaginacaoPadrao

    def get_queryset(self):
        qs = (
            PecasReposicao.objects
            .filter(ativo=True)
            .prefetch_related("imagem_peca_reposicao")
            .order_by("nome")
        )

        busca = self.request.query_params.get("busca")
        if busca:
            qs = qs.filter(nome__icontains=busca)

        return qs

    @method_decorator(cache_page(CACHE_CATALOGO))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


class PecaDetalheAPI(generics.RetrieveAPIView):
    serializer_class = PecaSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return (
            PecasReposicao.objects
            .filter(ativo=True)
            .prefetch_related("imagem_peca_reposicao")
        )
    