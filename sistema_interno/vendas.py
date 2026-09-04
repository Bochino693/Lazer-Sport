"""Vendas: a entrada de dinheiro virando registro, documento e estatística.

TRÊS PORTAS, UM CAIXA. A empresa recebe por três caminhos -- a proposta
comercial (orçamento), a ordem de serviço e o pedido da loja -- e cada um
guardava o seu dinheiro do seu jeito. A tela financeira somava só o da
loja: uma proposta de R$ 20.000 paga no balcão não existia no gráfico.

Aqui os três viram a mesma unidade: a VENDA, que é uma parcela recebida,
com valor, data e origem (ver `Venda`, em models.py). O pedido da loja
continua no `core.Venda` de sempre e é lido de lá; orçamento e O.S.
passam a registrar cada parcela por esta porta.

POR QUE PARCELA, E NÃO SALDO. `Orcamento.valor_pago` é um acumulado: ele
é sobrescrito a cada pagamento e não sabe QUANDO cada pedaço entrou. Com
entrada em janeiro e o resto em abril, o mês de janeiro ficava vazio e
abril recebia o valor inteiro. A parcela é a diferença entre o que o
documento passou a ter e o que já estava registrado aqui.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.db.models import Count, DecimalField, Sum, Value
from django.db.models.functions import Coalesce, TruncMonth
from django.utils import timezone

from core.models import Venda as VendaDaLoja

from .models import Orcamento, OrdemServico, Venda

ZERO = Decimal("0.00")


def _dinheiro(valor) -> Decimal:
    return (valor or ZERO).quantize(Decimal("0.01"))


def _campo_de_origem(documento):
    if isinstance(documento, Orcamento):
        return "orcamento", Venda.Origem.ORCAMENTO
    if isinstance(documento, OrdemServico):
        return "ordem_servico", Venda.Origem.ORDEM_SERVICO
    raise TypeError(
        "Só orçamento e ordem de serviço registram venda por aqui."
    )


def total_registrado(documento) -> Decimal:
    """Quanto deste documento já virou venda (fora as canceladas)."""
    campo, _ = _campo_de_origem(documento)
    if not documento.pk:
        return ZERO

    soma = (
        Venda.objects
        .filter(**{campo: documento})
        .exclude(situacao=Venda.Situacao.CANCELADA)
        .aggregate(
            total=Coalesce(
                Sum("valor"),
                Value(ZERO, output_field=DecimalField(max_digits=14, decimal_places=2)),
            )
        )["total"]
    )
    return _dinheiro(soma)


@transaction.atomic
def registrar_parcela(documento, *, usuario=None, observacao="", quando=None):
    """Cria a venda da diferença entre o pago no documento e o já registrado.

    Devolve a venda criada, ou None quando não há nada novo -- o que
    acontece o tempo todo: salvar o mesmo valor de novo, corrigir uma
    observação, ou registrar um valor MENOR (estorno, digitação errada).
    Estorno não vira venda negativa aqui; ele é uma correção do documento,
    e quem conta a receita é a soma das parcelas que existiram.
    """
    campo, origem = _campo_de_origem(documento)
    ja_registrado = total_registrado(documento)
    pago = _dinheiro(documento.valor_pago)
    parcela = _dinheiro(pago - ja_registrado)

    if parcela <= ZERO:
        return None

    return Venda.objects.create(
        origem=origem,
        cliente=getattr(documento, "cliente", None),
        nome_cliente=(documento.destinatario or "")[:120],
        valor=parcela,
        valor_documento=_dinheiro(documento.total),
        forma_pagamento=(getattr(documento, "forma_pagamento", "") or "")[:120],
        observacao=(observacao or "")[:240],
        recebida_em=quando or timezone.now(),
        registrada_por=usuario if getattr(usuario, "pk", None) else None,
        **{campo: documento},
    )


def emitir_documento(venda):
    """Prepara o comprovante para o cliente assinar."""
    return venda.emitir_documento()


def venda_para_documento(documento, *, usuario=None):
    """A venda que o comprovante deste documento deve mostrar.

    Pega a última venda registrada; se não houver nenhuma -- documento
    pago antes desta tela existir, ou pagamento gravado direto no banco --,
    registra a parcela que falta agora, para o comprovante nunca sair sem
    lastro.
    """
    campo, _ = _campo_de_origem(documento)
    venda = (
        Venda.objects
        .filter(**{campo: documento})
        .exclude(situacao=Venda.Situacao.CANCELADA)
        .order_by("-recebida_em", "-id")
        .first()
    )
    if venda:
        return venda
    return registrar_parcela(documento, usuario=usuario)


# ======================================================================
# ESTATÍSTICA — as três origens somadas uma vez só
# ======================================================================
ROTULOS_DE_ORIGEM = {
    Venda.Origem.ORCAMENTO: "Orçamentos",
    Venda.Origem.ORDEM_SERVICO: "Ordens de serviço",
    Venda.Origem.LOJA: "Loja online",
}


def _mes(valor):
    if hasattr(valor, "date"):
        valor = valor.date()
    return valor.replace(day=1)


def recebido_por_mes(inicio):
    """{mês: {origem: valor}} desde `inicio`, em duas consultas.

    A loja vem do `core.Venda` (confirmada), que é onde o checkout grava;
    orçamento e O.S. vêm das parcelas. Nenhuma origem é contada duas
    vezes porque cada uma tem o seu registro, e eles não se sobrepõem.
    """
    resultado = {}

    internas = (
        Venda.objects
        .exclude(situacao=Venda.Situacao.CANCELADA)
        .filter(recebida_em__date__gte=inicio)
        .annotate(mes=TruncMonth("recebida_em"))
        .values("mes", "origem")
        .annotate(
            total=Coalesce(
                Sum("valor"),
                Value(ZERO, output_field=DecimalField(max_digits=14, decimal_places=2)),
            )
        )
    )
    for linha in internas:
        if not linha["mes"]:
            continue
        mes = resultado.setdefault(_mes(linha["mes"]), {})
        mes[linha["origem"]] = mes.get(linha["origem"], ZERO) + _dinheiro(linha["total"])

    loja = (
        VendaDaLoja.objects
        .filter(confirmado=True, criacao__date__gte=inicio)
        .annotate(mes=TruncMonth("criacao"))
        .values("mes")
        .annotate(
            total=Coalesce(
                Sum("valor_pago"),
                Value(ZERO, output_field=DecimalField(max_digits=14, decimal_places=2)),
            )
        )
    )
    for linha in loja:
        if not linha["mes"]:
            continue
        mes = resultado.setdefault(_mes(linha["mes"]), {})
        chave = Venda.Origem.LOJA
        mes[chave] = mes.get(chave, ZERO) + _dinheiro(linha["total"])

    return resultado


def receita_por_mes(inicio):
    """{mês: total recebido}, somando as três origens."""
    return {
        mes: _dinheiro(sum(valores.values(), ZERO))
        for mes, valores in recebido_por_mes(inicio).items()
    }


def resumo_por_origem(inicio=None):
    """Quantidade e valor recebido em cada origem, para os cartões."""
    internas = (
        Venda.objects
        .exclude(situacao=Venda.Situacao.CANCELADA)
        .filter(**({"recebida_em__date__gte": inicio} if inicio else {}))
        .values("origem")
        .annotate(
            quantidade=Count("pk"),
            total=Coalesce(
                Sum("valor"),
                Value(ZERO, output_field=DecimalField(max_digits=14, decimal_places=2)),
            ),
        )
    )
    por_origem = {
        linha["origem"]: {
            "quantidade": linha["quantidade"],
            "total": _dinheiro(linha["total"]),
        }
        for linha in internas
    }

    loja = (
        VendaDaLoja.objects
        .filter(confirmado=True, **({"criacao__date__gte": inicio} if inicio else {}))
        .aggregate(
            quantidade=Count("pk"),
            total=Coalesce(
                Sum("valor_pago"),
                Value(ZERO, output_field=DecimalField(max_digits=14, decimal_places=2)),
            ),
        )
    )
    por_origem[Venda.Origem.LOJA] = {
        "quantidade": loja["quantidade"] or 0,
        "total": _dinheiro(loja["total"]),
    }

    return [
        {
            "codigo": codigo,
            "rotulo": rotulo,
            "quantidade": por_origem.get(codigo, {}).get("quantidade", 0),
            "total": por_origem.get(codigo, {}).get("total", ZERO),
        }
        for codigo, rotulo in ROTULOS_DE_ORIGEM.items()
    ]


def a_documentar():
    """Vendas com dinheiro na conta e comprovante ainda não emitido.

    É a fila de trabalho da tela: cada linha aqui é um cliente que pagou
    e ainda não assinou nada.
    """
    return (
        Venda.objects
        .filter(situacao=Venda.Situacao.REGISTRADA)
        .select_related("orcamento", "ordem_servico", "cliente")
    )


def indicadores(inicio=None):
    """Números grandes do topo da tela de vendas."""
    origens = resumo_por_origem(inicio)
    total = _dinheiro(sum((linha["total"] for linha in origens), ZERO))
    quantidade = sum(linha["quantidade"] for linha in origens)

    assinadas = Venda.objects.filter(situacao=Venda.Situacao.ASSINADA).count()
    pendentes = Venda.objects.filter(
        situacao__in=(Venda.Situacao.REGISTRADA, Venda.Situacao.DOCUMENTO_EMITIDO)
    ).count()

    return {
        "origens": origens,
        "total_recebido": total,
        "quantidade_vendas": quantidade,
        "ticket_medio": _dinheiro(total / quantidade) if quantidade else ZERO,
        "documentos_assinados": assinadas,
        "documentos_pendentes": pendentes,
    }


def em_aberto_por_documento():
    """Quanto ainda falta receber, somado por tipo de documento.

    Sai dos próprios documentos (proposta aprovada e O.S. viva), porque
    saldo a receber não é venda: é promessa. Fica separado do recebido de
    propósito -- misturar os dois é como uma empresa descobre tarde que
    faturou no papel e não no caixa.
    """
    aprovados = Orcamento.objects.filter(status=Orcamento.Status.APROVADO)
    a_receber_orcamentos = sum(
        (orcamento.saldo_pagamento for orcamento in aprovados),
        ZERO,
    )

    ordens = OrdemServico.objects.exclude(
        status__in=(
            OrdemServico.Status.RASCUNHO,
            OrdemServico.Status.CANCELADA,
            OrdemServico.Status.SUBSTITUIDA,
        )
    )
    a_receber_ordens = sum(
        (ordem.saldo_pagamento for ordem in ordens),
        ZERO,
    )

    return {
        "orcamentos": _dinheiro(a_receber_orcamentos),
        "ordens_servico": _dinheiro(a_receber_ordens),
        "total": _dinheiro(a_receber_orcamentos + a_receber_ordens),
    }


MESES_CURTOS = (
    "jan", "fev", "mar", "abr", "mai", "jun",
    "jul", "ago", "set", "out", "nov", "dez",
)


def serie_mensal(meses):
    """Barra empilhada por mês: quanto veio de cada origem.

    Empilhada, e não três barras lado a lado: a pergunta que a tela
    responde primeiro é "quanto entrou neste mês", e a composição vem
    depois. Três barras separadas invertem essa ordem e obrigam a somar
    de cabeça.

    As alturas saem daqui em porcentagem, prontas para o CSS -- o gráfico
    é desenhado no servidor, sem biblioteca e sem uma segunda requisição.
    """
    recebido = recebido_por_mes(meses[0])
    linhas = []

    for mes in meses:
        valores = recebido.get(mes, {})
        total = _dinheiro(sum(valores.values(), ZERO))
        linhas.append({
            "mes": mes,
            "rotulo": MESES_CURTOS[mes.month - 1],
            "rotulo_longo": f"{MESES_CURTOS[mes.month - 1]}/{mes.year}",
            "total": total,
            "partes": [
                {
                    "codigo": codigo,
                    "rotulo": rotulo,
                    "valor": _dinheiro(valores.get(codigo, ZERO)),
                }
                for codigo, rotulo in ROTULOS_DE_ORIGEM.items()
            ],
        })

    teto = max((linha["total"] for linha in linhas), default=ZERO)

    for linha in linhas:
        # Uma barra de valor zero fica com 0% e ganha um traço mínimo no
        # CSS: some da leitura como valor, mas o mês continua no eixo.
        linha["altura"] = (
            round(float(linha["total"] / teto) * 100, 2) if teto > 0 else 0
        )
        for parte in linha["partes"]:
            parte["altura"] = (
                round(float(parte["valor"] / linha["total"]) * 100, 2)
                if linha["total"] > 0
                else 0
            )

    return linhas, teto


def ultimas(limite=40):
    """As vendas mais recentes das três origens, já ordenadas juntas.

    A lista é curta de propósito: quem abre a tela quer ver o que entrou,
    não auditar o ano. O relatório do período fica nos números do topo e
    no gráfico.
    """
    internas = list(
        Venda.objects
        .exclude(situacao=Venda.Situacao.CANCELADA)
        .select_related("orcamento", "ordem_servico", "cliente", "aceite_eletronico")
        .order_by("-recebida_em", "-id")[:limite]
    )

    loja = list(
        VendaDaLoja.objects
        .filter(confirmado=True)
        .select_related("pedido", "pedido__cliente__user")
        .order_by("-criacao", "-id")[:limite]
    )

    linhas = [
        {
            "tipo": "interna",
            "venda": venda,
            "origem": venda.get_origem_display(),
            "codigo_origem": venda.origem,
            "documento": (
                venda.documento_de_origem.numero_documento
                if venda.documento_de_origem
                else "—"
            ),
            "cliente": venda.destinatario,
            "valor": venda.valor,
            "quando": venda.recebida_em,
            "assinada": venda.assinada,
            "situacao": venda.get_situacao_display(),
        }
        for venda in internas
    ]

    for venda in loja:
        cliente = getattr(getattr(venda.pedido, "cliente", None), "user", None)
        linhas.append({
            "tipo": "loja",
            "venda": venda,
            "origem": ROTULOS_DE_ORIGEM[Venda.Origem.LOJA],
            "codigo_origem": Venda.Origem.LOJA,
            "documento": f"Pedido #{venda.pedido_id}" if venda.pedido_id else "—",
            "cliente": (
                (cliente.get_full_name() or cliente.username)
                if cliente else "Cliente do site"
            ),
            "valor": _dinheiro(venda.valor_pago),
            "quando": venda.criacao,
            "assinada": False,
            "situacao": "Confirmada",
        })

    linhas.sort(key=lambda linha: linha["quando"] or timezone.now(), reverse=True)
    return linhas[:limite]
