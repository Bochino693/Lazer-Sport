"""AS MÉTRICAS DE VENDA, UNIFICADAS (LEIA-ME-V10, seção 147).

O dono: "tudo deve ir para a mesma métrica" -- o orçamento, a O.S. e o
pedido do site. Decisões dele:

  * TRÊS CANAIS. "Site" (o pedido pago), "Orçamento" (o orçamento pago
    100%) e "Serviços" (a O.S. paga), cada um na sua linha e todos no total.
  * SEM CONTAR DUAS VEZES. O site e o orçamento já viram a mesma
    `core.Venda`, uma por origem (seção 89). A O.S. não tem venda: entra
    pelo pagamento dela -- e a O.S. que nasceu de um orçamento que já virou
    venda NÃO conta de novo (o dinheiro dela está na venda do orçamento).
  * O QUE É "VENDA" AQUI. Site: a venda de pedido que não foi cancelado.
    Orçamento: a venda do orçamento (existe só enquanto ele está 100% pago).
    Serviços: a O.S. paga, que não foi cancelada nem trocada por outra
    versão. A data é a do pagamento (a venda nasce nele; na O.S., `pago_em`).

Além de quantidade, valor e ticket por canal: o tempo entre as fases (a
mediana, que uma venda parada não distorce), a taxa de assinatura e o tempo
para assinar.

Tudo numa conta FIXA de consultas (o banco fica longe): as vendas, as O.S.,
os documentos assinados e os itens dos pedidos do site, cada um de uma vez.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from statistics import median

from django.db.models import Q
from django.utils import timezone

from core.models import Venda

from .models import DocumentoAssinatura, OrdemServico

ZERO = Decimal("0.00")

#: Os períodos da tela (chips): a chave, o rótulo e quantos dias (None = tudo).
PERIODOS = (
    ("30", "30 dias", 30),
    ("90", "90 dias", 90),
    ("365", "12 meses", 365),
    ("tudo", "Tudo", None),
)
PERIODO_PADRAO = "90"

#: Os canais, na ordem da tela: chave, rótulo, ícone (Bootstrap Icons), cor.
CANAIS = (
    ("site", "Site", "bi-globe2", "blue"),
    ("orcamento", "Orçamento", "bi-file-earmark-text", "green"),
    ("servicos", "Serviços", "bi-wrench-adjustable", "violet"),
)


def ler_periodo(valor) -> str:
    valor = (valor or "").strip()
    return valor if valor in {chave for chave, _, _ in PERIODOS} else PERIODO_PADRAO


def inicio_do_periodo(periodo, agora=None):
    dias = {chave: dias for chave, _, dias in PERIODOS}[ler_periodo(periodo)]
    if dias is None:
        return None
    return (agora or timezone.now()) - timedelta(days=dias)


def texto_do_tempo(duracao) -> str:
    """A duração em palavra curta: "3 dias", "5 h", "20 min"; "—" sem dado."""
    if duracao is None:
        return "—"
    segundos = max(duracao.total_seconds(), 0)
    if segundos < 3600:
        return f"{max(round(segundos / 60), 1)} min"
    if segundos < 48 * 3600:
        return f"{round(segundos / 3600)} h"
    dias = round(segundos / 86400)
    return f"{dias} dias"


def _mediana(duracoes):
    duracoes = [d for d in duracoes if d is not None and d.total_seconds() >= 0]
    if not duracoes:
        return None
    return timedelta(seconds=median(d.total_seconds() for d in duracoes))


def _entre(inicio, fim):
    return (fim - inicio) if (inicio and fim) else None


@dataclass
class Canal:
    chave: str
    rotulo: str
    icone: str
    cor: str
    quantidade: int = 0
    valor: Decimal = ZERO
    #: quantas pedem assinatura e quantas têm o documento assinado
    pedem_assinatura: int = 0
    assinadas: int = 0
    tempos_para_assinar: list = field(default_factory=list)

    @property
    def ticket(self):
        return (self.valor / self.quantidade).quantize(Decimal("0.01")) if self.quantidade else ZERO

    @property
    def taxa_assinatura(self):
        """A % das vendas que pedem assinatura e já têm o documento assinado (None sem base)."""
        if not self.pedem_assinatura:
            return None
        return round(self.assinadas * 100 / self.pedem_assinatura)

    @property
    def tempo_para_assinar(self):
        return _mediana(self.tempos_para_assinar)

    @property
    def tempo_para_assinar_texto(self):
        return texto_do_tempo(self.tempo_para_assinar)


@dataclass
class Fase:
    canal: str
    nome: str
    tempo: timedelta | None
    base: int

    @property
    def texto(self):
        return texto_do_tempo(self.tempo)


def _servicos(inicio):
    """As O.S. pagas que contam como venda de serviço (sem as que já são venda de orçamento)."""
    consulta = (
        OrdemServico.objects
        .filter(status_pagamento=OrdemServico.StatusPagamento.PAGO)
        .exclude(status__in=(OrdemServico.Status.CANCELADA, OrdemServico.Status.SUBSTITUIDA))
        # a O.S. do orçamento que já virou venda não conta de novo
        .exclude(orcamento__venda__isnull=False)
        .only("id", "valor_pago", "pago_em", "criacao", "concluida_em", "orcamento_id", "status")
    )
    if inicio is not None:
        consulta = consulta.filter(pago_em__gte=inicio)
    return list(consulta)


def apurar(periodo=PERIODO_PADRAO, agora=None) -> dict:
    """Os números da tela para o período ("30", "90", "365" ou "tudo")."""
    from . import documento_pedido

    periodo = ler_periodo(periodo)
    inicio = inicio_do_periodo(periodo, agora)
    canais = {chave: Canal(chave, rotulo, icone, cor) for chave, rotulo, icone, cor in CANAIS}

    # ---- as vendas (site e orçamento): a mesma tabela, uma por origem
    vendas = Venda.objects.select_related("pedido", "orcamento").order_by("id")
    if inicio is not None:
        vendas = vendas.filter(criacao__gte=inicio)
    do_site, de_orcamento, sem_origem = [], [], 0
    for venda in vendas:
        if venda.pedido_id:
            if venda.pedido.status != "cancelado":
                do_site.append(venda)
        elif getattr(venda, "orcamento", None) is not None:
            de_orcamento.append(venda)
        else:
            sem_origem += 1
    servicos = _servicos(inicio)

    for venda in do_site:
        canais["site"].quantidade += 1
        canais["site"].valor += venda.valor_pago or ZERO
    for venda in de_orcamento:
        canais["orcamento"].quantidade += 1
        canais["orcamento"].valor += venda.valor_pago or ZERO
    for ordem in servicos:
        canais["servicos"].quantidade += 1
        canais["servicos"].valor += ordem.valor_pago or ZERO

    # ---- as assinaturas: os documentos assinados das três origens, numa consulta
    pedidos_ids = [v.pedido_id for v in do_site]
    orcamentos = {v.orcamento.pk: v.orcamento for v in de_orcamento}
    ordens = {o.pk: o for o in servicos}
    assinado = {"pedido": {}, "orcamento": {}, "ordem": {}}
    if pedidos_ids or orcamentos or ordens:
        for doc in (
            DocumentoAssinatura.objects
            .filter(situacao=DocumentoAssinatura.Situacao.ASSINADO)
            .filter(
                Q(pedido_id__in=pedidos_ids)
                | Q(orcamento_id__in=list(orcamentos))
                | Q(ordem_servico_id__in=list(ordens), orcamento__isnull=True)
            )
            .values("pedido_id", "orcamento_id", "ordem_servico_id", "criacao", "assinado_em")
        ):
            if doc["pedido_id"]:
                assinado["pedido"][doc["pedido_id"]] = doc
            elif doc["orcamento_id"]:
                assinado["orcamento"][doc["orcamento_id"]] = doc
            else:
                assinado["ordem"][doc["ordem_servico_id"]] = doc

    # site: só o pedido com máquina ou brinquedo pede contrato (seção 145);
    # conta-se o tempo desde o pagamento, quando o cliente já podia assinar
    if pedidos_ids:
        from django.db.models import prefetch_related_objects

        # os itens dos pedidos que a venda já trouxe, de uma vez
        pedidos = [v.pedido for v in do_site]
        prefetch_related_objects(pedidos, "itens__item_original")
        pedem = documento_pedido.quais_pedem_contrato(pedidos)
        for pedido in pedidos:
            # pede contrato quem leva máquina -- ou quem já tem um assinado
            if pedido.pk not in pedem and pedido.pk not in assinado["pedido"]:
                continue
            canais["site"].pedem_assinatura += 1
            doc = assinado["pedido"].get(pedido.pk)
            if doc:
                canais["site"].assinadas += 1
                canais["site"].tempos_para_assinar.append(_entre(pedido.pago_em, doc["assinado_em"]))
    # orçamento: toda venda pede o contrato; o tempo conta da aprovação
    for pk, orcamento in orcamentos.items():
        canais["orcamento"].pedem_assinatura += 1
        doc = assinado["orcamento"].get(pk)
        if doc:
            canais["orcamento"].assinadas += 1
            canais["orcamento"].tempos_para_assinar.append(
                _entre(orcamento.respondido_em or doc["criacao"], doc["assinado_em"])
            )
    # serviços: a O.S. assinada (seção 124); o tempo conta de quando o documento saiu
    for pk in ordens:
        canais["servicos"].pedem_assinatura += 1
        doc = assinado["ordem"].get(pk)
        if doc:
            canais["servicos"].assinadas += 1
            canais["servicos"].tempos_para_assinar.append(_entre(doc["criacao"], doc["assinado_em"]))

    # ---- o tempo entre as fases (a mediana de quem passou pelas duas)
    def fase(canal, nome, pares):
        duracoes = [d for d in (_entre(a, b) for a, b in pares) if d is not None and d.total_seconds() >= 0]
        return Fase(canal, nome, _mediana(duracoes), len(duracoes))

    pedidos_das_vendas = [v.pedido for v in do_site]
    fases = [
        fase("Site", "Do pedido ao pagamento", [(p.criacao, p.pago_em) for p in pedidos_das_vendas]),
        fase("Site", "Do pagamento à saída (ou pronto para retirada)", [(p.pago_em, p.enviado_em) for p in pedidos_das_vendas]),
        fase("Site", "Do pagamento à entrega", [(p.pago_em, p.entregue_em) for p in pedidos_das_vendas]),
        fase("Orçamento", "Da proposta enviada à aprovação", [(o.enviado_em, o.respondido_em) for o in orcamentos.values()]),
        fase("Orçamento", "Da aprovação ao pagamento completo", [(o.respondido_em, o.pago_em) for o in orcamentos.values()]),
        fase("Serviços", "Da abertura da O.S. ao pagamento", [(o.criacao, o.pago_em) for o in servicos]),
        fase("Serviços", "Da abertura da O.S. à conclusão", [(o.criacao, o.concluida_em) for o in servicos]),
    ]

    lista = [canais[chave] for chave, *_ in CANAIS]
    quantidade = sum(c.quantidade for c in lista)
    valor = sum((c.valor for c in lista), ZERO)
    pedem = sum(c.pedem_assinatura for c in lista)
    assinadas = sum(c.assinadas for c in lista)
    for canal in lista:
        canal.parte = round(canal.valor * 100 / valor) if valor else 0
    return {
        "periodo": periodo,
        "inicio": inicio,
        "canais": lista,
        "quantidade": quantidade,
        "valor": valor,
        "ticket": (valor / quantidade).quantize(Decimal("0.01")) if quantidade else ZERO,
        "pedem_assinatura": pedem,
        "assinadas": assinadas,
        "taxa_assinatura": round(assinadas * 100 / pedem) if pedem else None,
        "tempo_para_assinar": texto_do_tempo(_mediana([t for c in lista for t in c.tempos_para_assinar])),
        "fases": fases,
        # venda antiga sem pedido nem orçamento (não entra em canal nenhum)
        "sem_origem": sem_origem,
    }
