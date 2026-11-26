"""MEUS PEDIDOS, CENTRALIZADO (LEIA-ME-V10, seção 146).

O dono: "melhore também as informações do lado do cliente (...) em meus
pedidos, para centralizar os dados dos orçamentos, O.S. e pedidos do site".

Meus pedidos já mostrava os pedidos do site (as fases, a produção e, desde a
seção 145, o contrato) e os orçamentos vinculados pelo código (as fases, o
contrato, o Pix). Faltava:

  * A ORDEM DE SERVIÇO. A O.S. só chegava ao cliente pelo link que a equipe
    manda. Agora a O.S. do orçamento que a conta acompanha aparece no cartão
    dele: o número, a situação, a agenda, o botão para abrir (e assinar) e a
    cópia assinada. A O.S. que NÃO nasceu de um orçamento da conta não tem
    como ser ligada a uma conta do site com segurança -- continua pelo link.
  * A FOTO de cada item do orçamento (inteira, a regra da seção 141).
  * O QUE FALTA FAZER, num lugar só: pagar, responder a proposta, assinar o
    contrato (do orçamento e do pedido do site), assinar a O.S. -- cada um
    levando ao cartão dele.

Só dados da própria conta; nada de dado interno. E numa conta fixa de
consultas: as O.S. e os documentos delas vêm de uma vez (o banco fica longe).
"""

from __future__ import annotations

from .models import DocumentoAssinatura, OrdemServico

ASSINADO = DocumentoAssinatura.Situacao.ASSINADO
ENCERRADAS = (OrdemServico.Status.CANCELADA, OrdemServico.Status.SUBSTITUIDA)


def _foto_do_item(item) -> str:
    """A foto do item do orçamento (a capa do brinquedo); "" sem foto. Sem consulta."""
    from core.fotos import reduzir_imagem, url_da_imagem

    try:
        brinquedo = item.brinquedo if item.brinquedo_id else None
        imagem = brinquedo.imagem_brinquedo if brinquedo is not None else None
        url = url_da_imagem(imagem) if imagem else ""
        return reduzir_imagem(url, 200) if url else ""
    except Exception:  # noqa: BLE001 -- foto que não abre vira "sem foto"
        return ""


def _ordem_do_orcamento(orcamento):
    try:
        return orcamento.ordem_servico
    except OrdemServico.DoesNotExist:
        return None


def anotar_orcamentos(cartoes) -> None:
    """Põe em cada cartão de orçamento a foto dos itens e a O.S. dele (`cartao.ordem`).

    `cartao.ordem` é None quando não há O.S. que o cliente possa ver (não
    existe, ainda não foi enviada, ou foi trocada por outra versão).
    """
    cartoes = list(cartoes)
    ordens = {}
    for cartao in cartoes:
        for item in cartao.itens:
            item.foto_url = _foto_do_item(item)
        ordem = _ordem_do_orcamento(cartao.orcamento)
        cartao.ordem = None
        if ordem is not None and ordem.enviada_em and ordem.status != OrdemServico.Status.SUBSTITUIDA:
            ordens[ordem.pk] = (cartao, ordem)
    if not ordens:
        return
    # os documentos de assinatura das O.S., todos de uma vez
    documentos = {}
    for documento in (
        DocumentoAssinatura.objects
        .filter(ordem_servico_id__in=list(ordens))
        .exclude(situacao=DocumentoAssinatura.Situacao.SUBSTITUIDO)
        .defer("assinatura_png", "diario", "conteudo")
        .order_by("id")
    ):
        documentos[documento.ordem_servico_id] = documento
    from django.urls import reverse

    for pk, (cartao, ordem) in ordens.items():
        documento = documentos.get(pk)
        cancelada = ordem.status == OrdemServico.Status.CANCELADA
        assinada = bool(documento and documento.situacao == ASSINADO)
        cartao.ordem = {
            "numero": ordem.numero_documento,
            "situacao": ordem.get_status_display(),
            "cancelada": cancelada,
            "equipamento": ordem.equipamento or "",
            "agendada_para": ordem.agendada_para,
            "url": ordem.caminho_publico,
            "assinada": assinada,
            "assinada_em": documento.assinado_em if assinada else None,
            "url_assinada": (
                reverse("documento_assinado_publico", args=[documento.codigo_publico]) if assinada else ""
            ),
            # falta assinar: há um documento esperando e a O.S. ainda vale
            "falta_assinar": bool(documento and not assinada and not cancelada),
        }
        cartao.ordem_documento = documento


def documento_da_ordem_para_assinar(orcamento):
    """O documento da O.S. deste orçamento que o cliente pode assinar agora, ou None."""
    ordem = _ordem_do_orcamento(orcamento)
    if ordem is None or not ordem.enviada_em or ordem.status in ENCERRADAS:
        return None
    documento = (
        DocumentoAssinatura.objects
        .filter(ordem_servico=ordem)
        .exclude(situacao=DocumentoAssinatura.Situacao.SUBSTITUIDO)
        .defer("assinatura_png")
        .order_by("-id")
        .first()
    )
    if documento is None or documento.situacao == ASSINADO:
        return None
    return documento


def o_que_falta(pedidos, cartoes) -> list[dict]:
    """O que o cliente ainda tem para fazer, na ordem em que aparece na página."""
    falta = []
    for cartao in cartoes:
        orcamento = cartao.orcamento
        ancora = f"orc-{orcamento.codigo}"
        nome = f"Orçamento {orcamento.codigo}"
        if cartao.pode_responder:
            falta.append({"texto": f"{nome}: responder a proposta", "icone": "fa-file-lines", "ancora": ancora})
        if cartao.pode_assinar:
            falta.append({"texto": f"{nome}: assinar o contrato", "icone": "fa-signature", "ancora": ancora})
        ordem = getattr(cartao, "ordem", None)
        if ordem and ordem["falta_assinar"]:
            falta.append({"texto": f"O.S. {ordem['numero']}: assinar a ordem de serviço", "icone": "fa-signature", "ancora": ancora})
    for pedido in pedidos:
        ancora = f"pedido-{pedido.pk}"
        if pedido.status == "aguardando_pagamento":
            falta.append({"texto": f"Pedido #{pedido.pk}: concluir o pagamento", "icone": "fa-clock", "ancora": ancora})
        contrato = getattr(pedido, "contrato", None)
        if contrato and contrato["situacao"] == "assinar":
            falta.append({"texto": f"Pedido #{pedido.pk}: assinar o contrato", "icone": "fa-signature", "ancora": ancora})
    return falta
