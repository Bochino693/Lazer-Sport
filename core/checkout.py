"""Ciclo de vida do checkout: carrinho -> pedido reservado -> pedido pago.

O desenho anterior mantinha o carrinho como fonte da verdade até o pagamento
ser aprovado. Funcionava, mas deixava o cliente num limbo: ele pagava o Pix,
fechava a aba, e do lado dele continuava existindo um carrinho cheio e nenhum
pedido — sem contar o carrinho aparecendo e sumindo conforme a confirmação
chegava ou não.

Agora o compromisso é assumido no início do pagamento, como em qualquer loja
moderna:

    1. RESERVA   — ao gerar o Pix ou enviar o cartão, o carrinho vira um
                   Pedido com status "aguardando_pagamento". Os itens são
                   copiados para o pedido e o carrinho é esvaziado ali.
    2. CONFIRMA  — quando a cobrança é aprovada, o mesmo pedido passa para
                   "pago". Nada é criado nesse momento.
    3. DEVOLVE   — se a cobrança é recusada, cancelada ou expira, os itens
                   voltam para o carrinho e o pedido é cancelado.

Assim existe um único registro do começo ao fim, e o cliente sempre vê ou um
carrinho ou um pedido — nunca os dois, nunca nenhum.
"""

import hashlib
import json
import logging
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone

from .models import Carrinho, ItemPedido, Pedido

logger = logging.getLogger("core.payment")

# Status do Mercado Pago que encerram a cobrança sem pagamento.
STATUS_MORTOS = {"rejected", "cancelled", "refunded", "charged_back"}

# Status em que a cobrança ainda pode ser paga.
STATUS_VIVOS = {"pending", "in_process", "authorized"}


class ReservaInvalida(Exception):
    """O carrinho não está em condição de virar pedido."""


def valor_monetario(valor):
    """Converte e fixa qualquer valor financeiro em duas casas decimais."""
    try:
        return Decimal(str(valor)).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
    except (InvalidOperation, TypeError, ValueError):
        return None


# ======================================================================
# ASSINATURA
# ======================================================================
def assinatura_dos_itens(linhas, cupom_id, tipo_envio, frete, total):
    """Hash estável do conteúdo cobrado.

    Serve para dois carrinhos com o mesmo total, mas itens diferentes, nunca
    compartilharem cobrança nem chave de idempotência.
    """
    dados = {
        "itens": linhas,
        "cupom_id": cupom_id,
        "tipo_envio": tipo_envio,
        "frete": f"{frete:.2f}",
        "total_final": f"{total:.2f}",
    }
    serializado = json.dumps(
        dados,
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serializado.encode("utf-8")).hexdigest()


def assinatura_do_carrinho(carrinho):
    linhas = []
    queryset = (
        carrinho.itens
        .select_related("content_type")
        .order_by("content_type_id", "object_id", "id")
    )

    for item in queryset:
        preco = valor_monetario(item.preco_unitario)
        subtotal = valor_monetario(item.subtotal)
        if preco is None or subtotal is None:
            raise ReservaInvalida(
                f"O item {item.id} está com valor inválido."
            )
        linhas.append({
            "content_type_id": item.content_type_id,
            "object_id": item.object_id,
            "quantidade": item.quantidade,
            "preco_unitario": f"{preco:.2f}",
            "subtotal": f"{subtotal:.2f}",
        })

    frete = valor_monetario(carrinho.valor_frete)
    total = valor_monetario(carrinho.total_final)
    if frete is None or total is None:
        raise ReservaInvalida("O carrinho está com total inválido.")

    return assinatura_dos_itens(
        linhas,
        carrinho.cupom_id,
        carrinho.tipo_envio,
        frete,
        total,
    )


def assinatura_do_pedido(pedido):
    """Recalcula a assinatura a partir do que ficou gravado no pedido.

    Usada para conferir que o pedido reservado não foi adulterado entre a
    reserva e a confirmação.
    """
    linhas = []
    queryset = pedido.itens.order_by("content_type_id", "object_id", "id")

    for item in queryset:
        preco = valor_monetario(item.preco_unitario)
        subtotal = valor_monetario(item.subtotal)
        if preco is None or subtotal is None:
            raise ReservaInvalida(
                f"O item {item.id} do pedido está com valor inválido."
            )
        linhas.append({
            "content_type_id": item.content_type_id,
            "object_id": item.object_id,
            "quantidade": item.quantidade,
            "preco_unitario": f"{preco:.2f}",
            "subtotal": f"{subtotal:.2f}",
        })

    frete = valor_monetario(pedido.valor_frete) or Decimal("0.00")
    total = valor_monetario(pedido.total_final)
    if total is None:
        raise ReservaInvalida("O pedido está com total inválido.")

    return assinatura_dos_itens(
        linhas,
        pedido.carrinho_origem.cupom_id if pedido.carrinho_origem else None,
        pedido.tipo_envio,
        frete,
        total,
    )


# ======================================================================
# RESERVA
# ======================================================================
def pedido_reservado_do_carrinho(carrinho):
    """Reserva ainda viva para este carrinho, se houver."""
    return (
        Pedido.objects
        .filter(
            carrinho_origem=carrinho,
            status="aguardando_pagamento",
        )
        .order_by("-id")
        .first()
    )


@transaction.atomic
def reservar_pedido(carrinho, usuario=None):
    """Transforma o carrinho em um pedido aguardando pagamento.

    Idempotente: se já existe uma reserva viva com a mesma assinatura, ela é
    devolvida em vez de uma nova ser criada — atualizar a página de pagamento
    não pode gerar dois pedidos.
    """
    travado = (
        Carrinho.objects
        .select_for_update()
        .get(pk=carrinho.pk)
    )

    reserva = pedido_reservado_do_carrinho(travado)

    if reserva and not travado.itens.exists():
        # Reserva já feita e carrinho já esvaziado: é o caminho normal de
        # quem recarregou a página de pagamento.
        return reserva, False

    if not travado.itens.exists():
        raise ReservaInvalida("O carrinho está vazio.")

    if reserva:
        # Carrinho voltou a ter itens com uma reserva viva em aberto: o
        # cliente mexeu no carrinho depois de abrir o pagamento. A reserva
        # antiga não vale mais.
        logger.info(
            "Reserva %s descartada: carrinho %s foi alterado.",
            reserva.id,
            travado.id,
        )
        reserva.devolver_ao_carrinho()

    assinatura = assinatura_do_carrinho(travado)
    total = valor_monetario(travado.total_final)

    if total is None or total <= Decimal("0.00"):
        raise ReservaInvalida("O total do carrinho é inválido para pagamento.")

    frete = getattr(travado, "frete", None)
    cupom = travado.cupom

    pedido = Pedido.objects.create(
        cliente=travado.cliente,
        carrinho_origem=travado,
        status="aguardando_pagamento",
        tipo_envio=travado.tipo_envio,
        total_bruto=travado.total_bruto,
        valor_desconto=travado.valor_desconto,
        total_liquido=travado.total_liquido,
        valor_frete=valor_monetario(travado.valor_frete) or Decimal("0.00"),
        total_final=total,
        cep=frete.cep if frete else None,
        rua=frete.rua if frete else None,
        bairro=frete.bairro if frete else None,
        cidade=frete.cidade if frete else None,
        numero=frete.numero if frete else None,
        cupom_codigo=cupom.codigo if cupom else None,
        cupom_percentual=cupom.desconto_percentual if cupom else None,
        mp_fingerprint=assinatura,
    )

    ItemPedido.objects.bulk_create([
        ItemPedido(
            pedido=pedido,
            content_type=item.content_type,
            object_id=item.object_id,
            nome_item=str(item.item) if item.item else "Produto removido",
            tipo_item=item.content_type.model,
            preco_unitario=valor_monetario(item.preco_unitario) or Decimal("0.00"),
            quantidade=item.quantidade,
            subtotal=valor_monetario(item.subtotal) or Decimal("0.00"),
        )
        for item in travado.itens.select_related("content_type")
    ])

    # O carrinho se esvazia aqui: a partir de agora o compromisso está no
    # pedido, e é ele que o cliente vê em Meus Pedidos.
    travado.itens.all().delete()
    travado.cupom = None
    travado.save(update_fields=["cupom"])

    logger.info(
        "Pedido %s reservado a partir do carrinho %s (total %s).",
        pedido.id,
        travado.id,
        total,
    )
    return pedido, True


# ======================================================================
# CONFIRMAÇÃO
# ======================================================================
class PagamentoDivergente(Exception):
    """A cobrança recebida não corresponde ao pedido reservado."""


def pagamento_confere_com_pedido(payment, pedido):
    """A cobrança é exatamente deste pedido, pelo valor exato dele."""
    payment_id = str(payment.get("id") or "")
    valor_pago = valor_monetario(payment.get("transaction_amount"))
    valor_esperado = valor_monetario(pedido.total_final)
    referencia = str(payment.get("external_reference") or "")
    metadata = payment.get("metadata") or {}
    assinatura_mp = metadata.get("cart_fingerprint")

    if not payment_id or valor_pago is None or valor_esperado is None:
        return False

    if pedido.mp_payment_id and payment_id != str(pedido.mp_payment_id):
        return False

    if valor_pago != valor_esperado:
        return False

    if referencia != referencia_do_pedido(pedido):
        return False

    # A assinatura confirma que os itens cobrados são os que o pedido guarda.
    if not assinatura_mp or assinatura_mp != pedido.mp_fingerprint:
        return False

    return True


def referencia_do_pedido(pedido):
    """`external_reference` enviado ao Mercado Pago.

    O prefixo distingue as cobranças criadas por este fluxo das antigas, que
    mandavam o id do carrinho cru — sem ele, o pedido 12 e o carrinho 12
    seriam indistinguíveis na volta do webhook.
    """
    return f"pedido:{pedido.id}"


def forma_pagamento_mp(payment):
    tipo = payment.get("payment_type_id")
    if tipo == "credit_card":
        return "credito"
    if tipo == "debit_card":
        return "debito"
    return "pix"


def confirmar_pagamento(pedido, payment):
    """Marca o pedido reservado como pago. Devolve (pedido, mudou).

    Idempotente: uma segunda confirmação do mesmo pagamento — webhook e
    polling chegando juntos — encontra o pedido já pago e não faz nada.
    """
    payment_id = str(payment.get("id") or "")

    if not payment_id or payment.get("status") != "approved":
        raise PagamentoDivergente("O pagamento ainda não está aprovado.")

    with transaction.atomic():
        travado = Pedido.objects.select_for_update().get(pk=pedido.pk)

        if travado.status not in ("aguardando_pagamento", "pago"):
            raise PagamentoDivergente(
                f"O pedido está em '{travado.get_status_display()}' e não "
                "pode receber pagamento."
            )

        if travado.status == "pago" and travado.mp_payment_id == payment_id:
            return travado, False

        if not pagamento_confere_com_pedido(payment, travado):
            raise PagamentoDivergente(
                "O valor ou os itens pagos não correspondem ao pedido."
            )

        travado.status = "pago"
        travado.forma_pagamento = forma_pagamento_mp(payment)
        travado.mp_payment_id = payment_id
        travado.mp_status = "approved"
        travado.save(update_fields=[
            "status",
            "forma_pagamento",
            "mp_payment_id",
            "mp_status",
            "atualizado",
        ])

        # O carrinho guarda o payment_id como recibo do último checkout.
        if travado.carrinho_origem_id:
            Carrinho.objects.filter(pk=travado.carrinho_origem_id).update(
                mp_payment_id=payment_id,
            )

        # on_commit: a thread do e-mail lê o pedido pela pk em outra conexão,
        # e antes do commit a mudança ainda não existe para ela.
        from .notificacoes import enviar_confirmacao_de_compra

        transaction.on_commit(
            lambda: enviar_confirmacao_de_compra(travado)
        )

        logger.info(
            "Pedido %s confirmado pelo pagamento %s.",
            travado.id,
            payment_id,
        )
        return travado, True


# ======================================================================
# LOCALIZAÇÃO DO PEDIDO A PARTIR DA COBRANÇA
# ======================================================================
def pedido_da_cobranca(payment):
    """Descobre a qual pedido uma cobrança do Mercado Pago pertence.

    Aceita as duas formas de `external_reference`:
      - "pedido:<id>" — criadas por este fluxo;
      - "<id do carrinho>" — cobranças abertas antes desta mudança e que
        ainda podem ser pagas. Sem este ramo, um Pix gerado momentos antes
        do deploy voltaria pelo webhook sem destino.
    """
    payment_id = str(payment.get("id") or "")

    if payment_id:
        pedido = Pedido.objects.filter(mp_payment_id=payment_id).first()
        if pedido:
            return pedido

    referencia = str(payment.get("external_reference") or "")

    if referencia.startswith("pedido:"):
        return Pedido.objects.filter(pk=referencia.split(":", 1)[1]).first()

    if referencia.isdigit():
        carrinho = Carrinho.objects.filter(pk=referencia).first()
        if carrinho:
            return pedido_reservado_do_carrinho(carrinho)

    return None


def expirar_reserva(pedido, motivo=""):
    """Devolve os itens ao carrinho quando a cobrança morreu."""
    if pedido.status != "aguardando_pagamento":
        return False

    try:
        pedido.devolver_ao_carrinho()
    except ValueError:
        logger.exception(
            "Não foi possível devolver o pedido %s ao carrinho.",
            pedido.id,
        )
        return False

    logger.info(
        "Reserva %s devolvida ao carrinho%s.",
        pedido.id,
        f" ({motivo})" if motivo else "",
    )
    return True


def reservas_vencidas(horas=24):
    """Reservas paradas há tempo demais, para devolver ao carrinho."""
    limite = timezone.now() - timezone.timedelta(hours=horas)
    return Pedido.objects.filter(
        status="aguardando_pagamento",
        criacao__lt=limite,
    )
