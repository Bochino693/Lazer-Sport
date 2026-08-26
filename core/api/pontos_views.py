# core/api/pontos_views.py
#
# Pontos, metas e loja de cupons -- o lado do aplicativo.
#
# POR QUE SÓ AQUI. A curtida vale ponto e a curtida é exclusiva do
# aplicativo; a loja de cupons é o prêmio dessa exclusividade. Expor a
# mesma loja no site tiraria o motivo de instalar -- e o motivo é o que
# faz o cliente voltar sozinho, sem a empresa pagar por isso.
#
# O cupom resgatado, esse sim, vale no site: é onde a compra acontece.

from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core import pontos as servico
from core.models import RecompensaCupom


class RecompensaSerializer(serializers.ModelSerializer):
    disponivel = serializers.BooleanField(read_only=True)
    desconto = serializers.SerializerMethodField()

    class Meta:
        model = RecompensaCupom
        fields = [
            "id",
            "nome",
            "descricao",
            "custo_pontos",
            "desconto",
            "validade_dias",
            "estoque",
            "disponivel",
        ]

    def get_desconto(self, obj):
        # Texto pronto: cada tela do app formataria de um jeito.
        return f"{obj.desconto_percentual:.0f}%".replace(".", ",")


class PontosResumoAPI(APIView):
    """GET /api/v1/pontos/ -- saldo, metas e extrato do cliente."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        dados = servico.progresso(request.user)
        dados["extrato"] = [
            {
                "quando": linha.criacao,
                "pontos": linha.pontos,
                "descricao": linha.descricao or linha.get_origem_display(),
                "origem": linha.origem,
            }
            for linha in servico.extrato(request.user)
        ]
        return Response(dados)


class LojaCuponsAPI(APIView):
    """GET /api/v1/cupons/loja/ -- o que dá para trocar por pontos.

    Aberta sem login de propósito: o app precisa poder mostrar o prêmio
    antes de pedir cadastro. O resgate é que exige conta.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        recompensas = RecompensaCupom.objects.filter(ativo=True)
        saldo = servico.progresso(request.user)["saldo"]

        dados = RecompensaSerializer(recompensas, many=True).data
        for item, recompensa in zip(dados, recompensas):
            item["pode_resgatar"] = bool(
                recompensa.disponivel and saldo >= recompensa.custo_pontos
            )
            item["faltam"] = max(recompensa.custo_pontos - saldo, 0)

        return Response({"saldo": saldo, "recompensas": dados})


class ResgatarCupomAPI(APIView):
    """POST /api/v1/cupons/resgatar/ -- body: {"recompensa": 3}."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        dados = request.data if isinstance(request.data, dict) else {}

        try:
            resgate = servico.resgatar(request.user, dados.get("recompensa"))
        except servico.ErroDeResgate as erro:
            return Response(
                {"ok": False, "erro": str(erro)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({
            "ok": True,
            "cupom": {
                "codigo": resgate.cupom.codigo,
                "desconto": f"{resgate.recompensa.desconto_percentual:.0f}%",
                "expira_em": resgate.expira_em,
                "recompensa": resgate.recompensa.nome,
            },
            "saldo": servico.carteira_de(request.user).saldo,
            "mensagem": (
                f"Cupom {resgate.cupom.codigo} liberado. Use no carrinho do "
                "site antes da validade."
            ),
        })


class MeusCuponsAPI(APIView):
    """GET /api/v1/cupons/meus/ -- o que o cliente já resgatou."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            "cupons": [
                {
                    "codigo": resgate.cupom.codigo,
                    "recompensa": resgate.recompensa.nome,
                    "desconto": (
                        f"{resgate.recompensa.desconto_percentual:.0f}%"
                    ),
                    "resgatado_em": resgate.criacao,
                    "expira_em": resgate.expira_em,
                    "pontos_gastos": resgate.pontos_gastos,
                }
                for resgate in servico.meus_cupons(request.user)
            ]
        })
