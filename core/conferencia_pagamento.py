"""Conferência dos pagamentos sem depender do cliente parado na tela.

Compra normal: a pessoa gera o Pix, sai, paga no app do banco e volta
quando quiser -- pelo carrinho, pela tela de pagamento ou por Meus pedidos.
O webhook do Mercado Pago confirma sozinho; isto aqui é a rede de segurança
para quando ele atrasa ou falha: toda vez que o cliente volta, as reservas
abertas dele são conferidas no Mercado Pago e acertadas (paga, ainda
pendente, ou morreu e os itens voltam para o carrinho).

E o mínimo do cartão: abaixo dele o formulário de cartão do Mercado Pago não
tem bandeira nenhuma para mostrar e a área fica vazia. O valor vem da própria
conta (/v1/payment_methods), guardado por algumas horas.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

import mercadopago
import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from . import checkout
from .models import Pedido

logger = logging.getLogger("core.payment")

# Quanto tempo depois de pago o carrinho vazio ainda leva para Meus pedidos.
JANELA_DO_PAGO_RECENTE = timedelta(hours=2)
# Reservas mais velhas do que isto não são consultadas ao abrir uma tela.
JANELA_DAS_RESERVAS = timedelta(days=3)
CHAVE_PEDIDOS_VISTOS = "ls-pedidos-vistos-em"

URL_FORMAS = "https://api.mercadopago.com/v1/payment_methods"
CHAVE_MINIMO = "mp-cartao-minimo-v1"


def conferir_reserva(pedido, sdk=None):
    """Consulta a cobrança da reserva e acerta o pedido.

    Devolve "pago", "pendente", "encerrado" ou "erro". Nunca levanta.
    """
    if pedido.status == "cancelado":
        return "encerrado"
    if pedido.status != "aguardando_pagamento":
        return "pago"
    if not pedido.mp_payment_id:
        return "pendente"
    if not settings.MP_ACCESS_TOKEN:
        return "erro"
    try:
        sdk = sdk or mercadopago.SDK(settings.MP_ACCESS_TOKEN)
        payment = sdk.payment().get(pedido.mp_payment_id).get("response") or {}
    except Exception:
        logger.exception("Conferência: falha ao consultar pedido=%s", pedido.id)
        return "erro"

    status = payment.get("status")
    try:
        if status == "approved":
            checkout.confirmar_pagamento(pedido, payment)
            return "pago"
        if status in checkout.STATUS_MORTOS:
            checkout.expirar_reserva(pedido, f"conferência: {status}")
            return "encerrado"
    except checkout.PagamentoDivergente:
        logger.critical("Conferência: pagamento divergente pedido=%s", pedido.id)
        return "erro"
    except Exception:
        logger.exception("Conferência: falha ao acertar pedido=%s", pedido.id)
        return "erro"
    return "pendente"


def conferir_reservas_do_cliente(perfil, carrinho=None, limite=3):
    """Confere as reservas abertas recentes do cliente (ou só deste carrinho).

    Devolve os pedidos que ficaram pagos nesta conferência.
    """
    reservas = Pedido.objects.filter(
        cliente=perfil,
        status="aguardando_pagamento",
        mp_payment_id__isnull=False,
        criacao__gte=timezone.now() - JANELA_DAS_RESERVAS,
    ).exclude(mp_payment_id="")
    if carrinho is not None:
        reservas = reservas.filter(carrinho_origem=carrinho)

    reservas = list(reservas.order_by("-criacao")[:limite])
    if not reservas or not settings.MP_ACCESS_TOKEN:
        return []

    sdk = mercadopago.SDK(settings.MP_ACCESS_TOKEN)
    pagos = []
    for pedido in reservas:
        if conferir_reserva(pedido, sdk) == "pago":
            pedido.refresh_from_db()
            pagos.append(pedido)
    return pagos


def pago_recente_do_carrinho(carrinho, request=None):
    """O pedido deste carrinho que acabou de ser pago e o cliente não viu.

    "Não viu" = foi pago depois da última visita a Meus pedidos. Assim o
    carrinho vazio leva para os pedidos logo depois da compra, mas não
    prende quem já viu a compra e quer comprar de novo.
    """
    desde = timezone.now() - JANELA_DO_PAGO_RECENTE
    if request is not None:
        visto = request.session.get(CHAVE_PEDIDOS_VISTOS)
        if visto:
            try:
                visto_em = datetime.fromisoformat(visto)
                if timezone.is_naive(visto_em):
                    visto_em = timezone.make_aware(visto_em)
                desde = max(desde, visto_em)
            except (TypeError, ValueError):
                pass
    return (
        Pedido.objects
        .filter(carrinho_origem=carrinho, atualizado__gt=desde)
        .exclude(status__in=("aguardando_pagamento", "cancelado"))
        .order_by("-atualizado")
        .first()
    )


def marcar_pedidos_vistos(request):
    request.session[CHAVE_PEDIDOS_VISTOS] = timezone.now().isoformat()


def reserva_em_andamento(carrinho):
    return (
        Pedido.objects
        .filter(carrinho_origem=carrinho, status="aguardando_pagamento")
        .order_by("-criacao")
        .first()
    )


def minimo_do_cartao():
    """Menor valor aceito no cartão (crédito ou débito) nesta conta, ou None."""
    guardado = cache.get(CHAVE_MINIMO)
    if guardado is not None:
        return guardado or None

    token = getattr(settings, "MP_ACCESS_TOKEN", "") or ""
    if not token:
        return None
    try:
        resposta = requests.get(
            URL_FORMAS,
            headers={"Authorization": f"Bearer {token}"},
            timeout=3,
        )
        formas = resposta.json() if resposta.status_code == 200 else None
    except (requests.RequestException, ValueError):
        formas = None

    if not isinstance(formas, list):
        cache.set(CHAVE_MINIMO, "", 5 * 60)
        return None

    minimos = []
    for forma in formas:
        if forma.get("status") != "active":
            continue
        if forma.get("payment_type_id") not in ("credit_card", "debit_card"):
            continue
        try:
            minimos.append(Decimal(str(forma.get("min_allowed_amount"))))
        except (InvalidOperation, TypeError):
            continue

    minimo = min(minimos) if minimos else None
    cache.set(CHAVE_MINIMO, minimo or "", 6 * 60 * 60)
    return minimo
