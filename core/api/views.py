# core/api/views.py
#
# Catálogo público + institucional + área logada.
#
# O endpoint /status/ existe pro app saber o que já está no ar antes de
# tentar. Sem ele o app fica adivinhando por 404 e mostra seção vazia
# sem explicação.

from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import (
    Brinquedos,
    CategoriasBrinquedos,
    ClientePerfil,
    Combos,
    Estabelecimentos,
    Eventos,
    Manutencao,
    PecasReposicao,
    Pedido,
    Promocoes,
)

from core.api.serializer import (
    BrinquedoDetalheSerializer,
    BrinquedoListaSerializer,
    CategoriaSerializer,
    ComboSerializer,
    EstabelecimentoSerializer,
    EventoSerializer,
    ManutencaoEscritaSerializer,
    ManutencaoLeituraSerializer,
    PecaSerializer,
    PedidoSerializer,
    PromocaoSerializer,
)

from django.db.models import Count, Q

# Curtidas na mesma consulta do catálogo: sem isto, cada item da lista
# faria a sua própria contagem.
ANOTACAO_CURTIDAS = Count(
    "favoritos",
    filter=Q(favoritos__tipo="curtida"),
    distinct=True,
)

CACHE_CATALOGO = 60 * 10

VERSAO_API = "1.3"

RECURSOS_DISPONIVEIS = [
    "auth",
    "categorias",
    "brinquedos",
    "pecas",
    "estabelecimentos",
    "eventos",
    "combos",
    "promocoes",
    "manutencoes",
    "pedidos",
    "favoritos",
    "pontos",
    "loja_cupons",
]


class PaginacaoPadrao(PageNumberPagination):
    page_size = 20
    page_size_query_param = "tamanho"
    max_page_size = 60


# ============================================================
# STATUS -- o app chama isto primeiro, na tela de abertura
# ============================================================

class StatusAPI(APIView):
    """GET /api/v1/status/

    Barato de propósito: sem query no banco. Serve pra:
      - o app saber se a API respondeu (splash e validações)
      - o app saber QUAIS seções já existem, em vez de tentar e
        receber 404 silencioso
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        recursos = list(RECURSOS_DISPONIVEIS)
        if "carrinho" not in recursos:
            recursos.append("carrinho")
        if "google" in settings.SOCIALACCOUNT_PROVIDERS:
            recursos.insert(1, "auth_google")

        return Response({
            "ok": True,
            "versao": VERSAO_API,
            "recursos": recursos,
            "minimo_app": "1.0",
        })


# ============================================================
# CATÁLOGO
# ============================================================

class CategoriaListAPI(generics.ListAPIView):
    serializer_class = CategoriaSerializer
    permission_classes = [AllowAny]
    pagination_class = None

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
            .prefetch_related("imagens_brinquedo")
            .annotate(total_curtidas=ANOTACAO_CURTIDAS)
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

        # Os filtros do docstring existiam só no papel: a versão anterior
        # montava o queryset acima e devolvia outro, sem categoria nem
        # busca. O app recebia o catálogo inteiro em toda tela.
        categoria = (self.request.query_params.get("categoria") or "").strip()
        if categoria.isdigit():
            qs = qs.filter(categorias_brinquedos__id=int(categoria))

        busca = (self.request.query_params.get("busca") or "").strip()
        if busca:
            qs = qs.filter(nome_brinquedo__icontains=busca)

        return qs.distinct()

    @method_decorator(cache_page(CACHE_CATALOGO))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


class BrinquedoDetalheAPI(generics.RetrieveAPIView):
    serializer_class = BrinquedoDetalheSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return (
            Brinquedos.objects
            .filter(ativo=True)
            .prefetch_related("categorias_brinquedos", "imagens_brinquedo")
            .annotate(total_curtidas=ANOTACAO_CURTIDAS)
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
            PecasReposicao.da_vitrine()
            .prefetch_related("imagem_peca_reposicao")
            .annotate(total_curtidas=ANOTACAO_CURTIDAS)
            .order_by("nome")
        )

        busca = (self.request.query_params.get("busca") or "").strip()
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
            PecasReposicao.da_vitrine()
            .prefetch_related("imagem_peca_reposicao")
            .annotate(total_curtidas=ANOTACAO_CURTIDAS)
        )


# ============================================================
# INSTITUCIONAL
# ============================================================

class EstabelecimentoListAPI(generics.ListAPIView):
    serializer_class = EstabelecimentoSerializer
    permission_classes = [AllowAny]
    pagination_class = PaginacaoPadrao

    def get_queryset(self):
        return (
            Estabelecimentos.objects
            .filter(ativo=True)
            .only("id", "nome_estabelecimento", "imagem_estabelecimento")
            .order_by("nome_estabelecimento")
        )

    @method_decorator(cache_page(CACHE_CATALOGO))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


class EventoListAPI(generics.ListAPIView):
    """Eventos não herdam de Prime -- não existe campo `ativo` aqui."""

    serializer_class = EventoSerializer
    permission_classes = [AllowAny]
    pagination_class = PaginacaoPadrao

    def get_queryset(self):
        return (
            Eventos.objects
            .prefetch_related("imagens_evento")
            .order_by("-id")
        )

    @method_decorator(cache_page(CACHE_CATALOGO))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


class ComboListAPI(generics.ListAPIView):
    serializer_class = ComboSerializer
    permission_classes = [AllowAny]
    pagination_class = PaginacaoPadrao

    def get_queryset(self):
        return Combos.objects.filter(ativo=True).order_by("descricao")

    @method_decorator(cache_page(CACHE_CATALOGO))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


class PromocaoListAPI(generics.ListAPIView):
    serializer_class = PromocaoSerializer
    permission_classes = [AllowAny]
    pagination_class = PaginacaoPadrao

    def get_queryset(self):
        return (
            Promocoes.objects
            .filter(ativo=True)
            .select_related("brinquedos")
            .order_by("-id")
        )

    @method_decorator(cache_page(CACHE_CATALOGO))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


# ============================================================
# ÁREA LOGADA
# ============================================================

def _perfil_do(request):
    perfil, _ = ClientePerfil.objects.get_or_create(
        user=request.user,
        defaults={
            "nome_completo": request.user.get_full_name() or "",
            "telefone": "",
        },
    )
    return perfil


class ManutencaoListCreateAPI(generics.ListCreateAPIView):
    """GET lista os chamados do cliente. POST abre um novo."""

    permission_classes = [IsAuthenticated]
    pagination_class = PaginacaoPadrao

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ManutencaoEscritaSerializer
        return ManutencaoLeituraSerializer

    def get_queryset(self):
        return (
            Manutencao.objects
            .filter(usuario__user=self.request.user)
            .select_related("brinquedo")
            .order_by("-criado_em")
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        chamado = serializer.save(usuario=_perfil_do(request))

        return Response(
            ManutencaoLeituraSerializer(chamado).data,
            status=status.HTTP_201_CREATED,
        )


class PedidoListAPI(generics.ListAPIView):
    serializer_class = PedidoSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = PaginacaoPadrao

    def get_queryset(self):
        return (
            Pedido.objects
            .filter(cliente__user=self.request.user)
            .prefetch_related("itens")
            .order_by("-criacao")
        )
