# core/api/carrinho_views.py
#
# SINCRONIZAÇÃO DO CARRINHO DO APP.
#
# O app monta o carrinho offline, no DataStore do aparelho — é o que
# permite navegar e escolher sem conexão. Mas o pagamento acontece no
# site, e para isso o carrinho precisa existir no Django.
#
# Esta rota é a ponte: o app manda a lista local, o Django reescreve o
# carrinho do cliente com ela e devolve o endereço do checkout. A partir
# daí vale o mesmo fluxo do site — a reserva vira pedido, o e-mail sai e
# o aviso aparece.
#
# É uma substituição, não uma soma: o aparelho é a fonte da verdade
# enquanto o cliente monta o pedido. Somar faria o item dobrar a cada
# sincronização repetida.

from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.urls import reverse
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core import checkout
from core.models import (
    Brinquedos,
    Carrinho,
    Combos,
    Cupom,
    ItemCarrinho,
    PecasReposicao,
    Promocoes,
)

# Os mesmos rótulos que o app usa em ItemCarrinho.tipo e que o
# ItemPedido.tipo_item já grava. Manter os quatro alinhados evita um item
# comprado no app aparecer sem tipo no pedido.
MODELOS_POR_TIPO = {
    "brinquedo": Brinquedos,
    "combo": Combos,
    "promocao": Promocoes,
    "pecas": PecasReposicao,
}

LIMITE_ITENS = 60
LIMITE_QUANTIDADE = 999


class ItemEnvioSerializer(serializers.Serializer):
    tipo = serializers.ChoiceField(choices=sorted(MODELOS_POR_TIPO))
    id = serializers.IntegerField(min_value=1)
    quantidade = serializers.IntegerField(
        min_value=1,
        max_value=LIMITE_QUANTIDADE,
        default=1,
    )


class CarrinhoEnvioSerializer(serializers.Serializer):
    itens = ItemEnvioSerializer(many=True)
    tipo_envio = serializers.ChoiceField(
        choices=[valor for valor, _ in Carrinho.TIPO_ENVIO],
        required=False,
    )
    cupom = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate_itens(self, valor):
        if len(valor) > LIMITE_ITENS:
            raise serializers.ValidationError(
                f"Um carrinho aceita no máximo {LIMITE_ITENS} itens."
            )
        return valor


class SincronizarCarrinhoAPI(APIView):
    """POST /api/v1/carrinho/sincronizar/"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        perfil = getattr(request.user, "perfil", None)
        if not perfil:
            return Response(
                {"detail": "Complete seu perfil antes de montar um pedido."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        entrada = CarrinhoEnvioSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        dados = entrada.validated_data

        with transaction.atomic():
            carrinho, _ = Carrinho.objects.get_or_create(cliente=perfil)
            carrinho = Carrinho.objects.select_for_update().get(pk=carrinho.pk)

            # Uma reserva aberta representa o carrinho de antes. Trocar o
            # conteúdo por baixo dela deixaria um pedido cobrando itens que
            # o cliente já não escolheu.
            reserva = checkout.pedido_reservado_do_carrinho(carrinho)
            if reserva:
                checkout.expirar_reserva(reserva, "carrinho sincronizado pelo app")
                carrinho.refresh_from_db()

            carrinho.itens.all().delete()

            criados, ignorados = self._gravar_itens(carrinho, dados["itens"])

            if "tipo_envio" in dados:
                carrinho.tipo_envio = dados["tipo_envio"]

            carrinho.cupom = self._resolver_cupom(dados.get("cupom"))

            # Qualquer cobrança anterior perde a validade junto com a
            # composição que ela representava.
            carrinho.mp_payment_id = None
            carrinho.save(
                update_fields=["tipo_envio", "cupom", "mp_payment_id"]
            )

        return Response({
            "ok": True,
            "carrinho_id": carrinho.id,
            "itens": criados,
            "ignorados": ignorados,
            "quantidade": sum(i.quantidade for i in carrinho.itens.all()),
            "total_bruto": f"{carrinho.total_bruto:.2f}",
            "total_final": f"{carrinho.total_final:.2f}",
            "checkout_url": request.build_absolute_uri(
                reverse("pagamento", args=[carrinho.id])
            ),
        })

    def _gravar_itens(self, carrinho, itens):
        """Grava os itens válidos e devolve (gravados, ignorados).

        Produto tirado do catálogo depois de o cliente colocá-lo no
        carrinho offline é ignorado em silêncio, e não derruba a
        sincronização inteira — o app já mostrou o item, a resposta diz
        quantos não vieram.
        """
        # Uma linha por produto: o app manda quantidade agregada, e duas
        # linhas do mesmo item violariam a leitura do carrinho no site.
        agrupados = {}
        for item in itens:
            chave = (item["tipo"], item["id"])
            agrupados[chave] = agrupados.get(chave, 0) + item["quantidade"]

        gravados = 0
        ignorados = 0

        for (tipo, objeto_id), quantidade in agrupados.items():
            modelo = MODELOS_POR_TIPO[tipo]

            if not modelo.objects.filter(pk=objeto_id).exists():
                ignorados += 1
                continue

            ItemCarrinho.objects.create(
                carrinho=carrinho,
                content_type=ContentType.objects.get_for_model(modelo),
                object_id=objeto_id,
                quantidade=min(quantidade, LIMITE_QUANTIDADE),
            )
            gravados += 1

        return gravados, ignorados

    @staticmethod
    def _resolver_cupom(codigo):
        """Cupom inválido não é erro: o pedido segue sem desconto."""
        codigo = (codigo or "").strip()
        if not codigo:
            return None

        return Cupom.objects.filter(codigo__iexact=codigo).first()
