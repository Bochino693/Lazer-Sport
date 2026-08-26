# core/api/favoritos_views.py
#
# Curtidas e lista de desejos para o aplicativo.
#
# Não exige login: sem token, o app manda a chave do aparelho no
# cabeçalho ``X-Dispositivo`` (32 hexadecimais gerados uma vez na
# instalação). Ao entrar na conta, o servidor migra o que estava no
# aparelho -- o app não precisa reenviar nada.
#
# As regras ficam em core/favoritos.py, as mesmas do site.

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core import favoritos as servico
from core.api.serializer import BrinquedoListaSerializer, PecaSerializer
from core.models import Favorito


def _resposta_com_dispositivo(request, dados, codigo=status.HTTP_200_OK):
    """Devolve a chave do aparelho para o app guardar na primeira vez."""
    dados["dispositivo"] = servico.chave_dispositivo(request)
    return Response(dados, status=codigo)


class FavoritoListaAPI(APIView):
    """GET /api/v1/favoritos/ -- o que este visitante já marcou."""

    permission_classes = [AllowAny]

    def get(self, request):
        marcados = {
            tipo: servico.ids_marcados(request, tipo)
            for tipo in (Favorito.Tipo.CURTIDA, Favorito.Tipo.DESEJO)
        }

        desejos = (
            servico.meus_favoritos(request, Favorito.Tipo.DESEJO)
            .select_related("brinquedo", "peca")
            .prefetch_related("peca__imagem_peca_reposicao")
        )

        brinquedos = [i.brinquedo for i in desejos if i.brinquedo_id and i.brinquedo]
        pecas = [i.peca for i in desejos if i.peca_id and i.peca]

        return _resposta_com_dispositivo(request, {
            "curtidas": {
                "brinquedos": sorted(marcados[Favorito.Tipo.CURTIDA]["brinquedo"]),
                "pecas": sorted(marcados[Favorito.Tipo.CURTIDA]["peca"]),
            },
            "lista_desejos": {
                "brinquedos": BrinquedoListaSerializer(
                    brinquedos,
                    many=True,
                    context={"request": request},
                ).data,
                "pecas": PecaSerializer(
                    pecas,
                    many=True,
                    context={"request": request},
                ).data,
            },
            "total_desejos": len(brinquedos) + len(pecas),
        })


class FavoritoAlternarAPI(APIView):
    """POST /api/v1/favoritos/alternar/

    Corpo: ``{"tipo": "curtida|desejo", "produto": "brinquedo|peca",
    "id": 12}``. Repetir a chamada desfaz a marcação.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        dados = request.data if isinstance(request.data, dict) else {}

        try:
            tipo = servico.normalizar_tipo(dados.get("tipo"))
            produto = servico.buscar_produto(dados.get("produto"), dados.get("id"))
        except servico.TipoInvalido:
            return Response(
                {"ok": False, "erro": "Tipo de interação inválido."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except servico.ProdutoInvalido:
            return Response(
                {"ok": False, "erro": "Produto não encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )

        estado = servico.alternar(
            request,
            tipo,
            produto,
            origem=Favorito.Origem.APP,
        )
        estado["ok"] = True
        estado["logado"] = servico.usuario_logado(request) is not None
        estado["total_desejos"] = servico.meus_favoritos(
            request,
            Favorito.Tipo.DESEJO,
        ).count()

        return _resposta_com_dispositivo(request, estado)
