"""Séries e indicadores do módulo financeiro do painel interno.

Os cálculos ficam aqui, fora da view, por dois motivos: o template recebe
números já prontos (sem lógica em `{% %}`) e os gráficos são desenhados em
SVG/CSS gerado no servidor — sem biblioteca de terceiros, sem uma requisição
extra a CDN e sem tela pulando enquanto o gráfico monta.
"""

from decimal import Decimal

from django.db.models import Count, DecimalField, F, Sum, Value
from django.db.models.functions import Coalesce, TruncMonth
from django.utils import timezone

from core.models import Venda

from .models import (
    ComprasMensais,
    DespesasMensais,
    EstoqueMaterial,
    Orcamento,
)

ZERO = Decimal("0.00")

MESES_CURTOS = (
    "jan", "fev", "mar", "abr", "mai", "jun",
    "jul", "ago", "set", "out", "nov", "dez",
)


def _dinheiro(valor):
    return (valor or ZERO).quantize(Decimal("0.01"))


def _primeiro_dia(data):
    return data.replace(day=1)


def _mes_anterior(data):
    """Volta um mês mantendo o dia 1. Evita depender de dateutil."""
    if data.month == 1:
        return data.replace(year=data.year - 1, month=12, day=1)
    return data.replace(month=data.month - 1, day=1)


def janela_de_meses(quantidade=12, referencia=None):
    """Lista dos N meses até a referência, do mais antigo ao mais novo."""
    fim = _primeiro_dia(referencia or timezone.localdate())

    meses = [fim]
    for _ in range(quantidade - 1):
        meses.append(_mes_anterior(meses[-1]))

    return list(reversed(meses))


def _somar_por_mes(queryset, campo_data, campo_valor):
    """{date(ano, mes, 1): Decimal} — uma query só, agrupada no banco."""
    linhas = (
        queryset
        .annotate(mes=TruncMonth(campo_data))
        .values("mes")
        .annotate(
            total=Coalesce(
                Sum(campo_valor),
                Value(ZERO, output_field=DecimalField(max_digits=14, decimal_places=2)),
            )
        )
    )

    resultado = {}
    for linha in linhas:
        if not linha["mes"]:
            continue
        chave = linha["mes"]
        # TruncMonth devolve datetime em campos DateTimeField.
        if hasattr(chave, "date"):
            chave = chave.date()
        resultado[chave.replace(day=1)] = _dinheiro(linha["total"])

    return resultado


def montar_series(meses):
    """Receita, despesa (despesas + compras) e lucro mês a mês."""
    inicio = meses[0]

    receitas = _somar_por_mes(
        Venda.objects.filter(confirmado=True, criacao__date__gte=inicio),
        "criacao",
        "valor_pago",
    )
    despesas = _somar_por_mes(
        DespesasMensais.objects.filter(criacao__date__gte=inicio),
        "criacao",
        "valor_despesa",
    )
    compras = _somar_por_mes(
        ComprasMensais.objects.filter(criacao__date__gte=inicio),
        "criacao",
        "valor",
    )

    serie = []
    for mes in meses:
        receita = receitas.get(mes, ZERO)
        saida = despesas.get(mes, ZERO) + compras.get(mes, ZERO)
        serie.append({
            "mes": mes,
            "rotulo": MESES_CURTOS[mes.month - 1],
            "rotulo_longo": f"{MESES_CURTOS[mes.month - 1]}/{mes.year}",
            "receita": _dinheiro(receita),
            "despesa": _dinheiro(despesas.get(mes, ZERO)),
            "compra": _dinheiro(compras.get(mes, ZERO)),
            "saida": _dinheiro(saida),
            "lucro": _dinheiro(receita - saida),
        })

    return serie


def aplicar_alturas(serie):
    """Converte os valores em porcentagem de altura para as barras do CSS.

    Uma barra de valor zero recebe 0% e ganha um traço mínimo no CSS: some
    da leitura como valor, mas o mês continua existindo no eixo.
    """
    valores = [linha["receita"] for linha in serie]
    valores += [linha["saida"] for linha in serie]
    teto = max(valores) if valores else ZERO

    for linha in serie:
        if teto > 0:
            linha["altura_receita"] = round(float(linha["receita"] / teto) * 100, 2)
            linha["altura_saida"] = round(float(linha["saida"] / teto) * 100, 2)
        else:
            linha["altura_receita"] = 0
            linha["altura_saida"] = 0

    return teto


def curva_de_lucro(serie, largura=560, altura=150):
    """Devolve os pontos do SVG da linha de lucro e a linha do zero.

    O eixo é simétrico em torno do zero para que prejuízo apareça abaixo da
    linha central em vez de ser espremido contra a base do gráfico.
    """
    if not serie:
        return {"pontos": "", "area": "", "linha_zero": altura / 2, "pico": ZERO}

    valores = [linha["lucro"] for linha in serie]
    pico = max((abs(valor) for valor in valores), default=ZERO)

    if pico <= 0:
        meio = altura / 2
        pontos = " ".join(
            f"{round(i * largura / max(len(serie) - 1, 1), 2)},{meio}"
            for i in range(len(serie))
        )
        return {"pontos": pontos, "area": "", "linha_zero": meio, "pico": ZERO}

    passo = largura / max(len(serie) - 1, 1)
    meio = altura / 2
    coordenadas = []

    for i, valor in enumerate(valores):
        x = round(i * passo, 2)
        # Metade da altura é o alcance de cada lado do zero.
        y = round(meio - (float(valor) / float(pico)) * (meio - 8), 2)
        coordenadas.append((x, y))

    pontos = " ".join(f"{x},{y}" for x, y in coordenadas)
    area = (
        f"{coordenadas[0][0]},{meio} "
        + pontos
        + f" {coordenadas[-1][0]},{meio}"
    )

    return {"pontos": pontos, "area": area, "linha_zero": meio, "pico": pico}


def despesas_por_categoria(inicio, limite=6):
    """Fatias do donut: categoria, valor, porcentagem e offset do traço."""
    linhas = (
        DespesasMensais.objects
        .filter(criacao__date__gte=inicio)
        .values("categoria_despesa__nome_categoria")
        .annotate(
            total=Coalesce(
                Sum("valor_despesa"),
                Value(ZERO, output_field=DecimalField(max_digits=14, decimal_places=2)),
            ),
            itens=Count("id"),
        )
        .order_by("-total")
    )

    linhas = list(linhas)
    total = sum((linha["total"] for linha in linhas), ZERO)

    cores = ("#6695ff", "#48d69e", "#f2bb64", "#a992ff", "#56c7e5", "#ff7184")

    fatias = []
    acumulado = 0.0

    for i, linha in enumerate(linhas[:limite]):
        fatia = float(linha["total"] / total) * 100 if total else 0.0
        fatias.append({
            "nome": linha["categoria_despesa__nome_categoria"] or "Sem categoria",
            "valor": _dinheiro(linha["total"]),
            "itens": linha["itens"],
            "percentual": round(fatia, 1),
            # stroke-dasharray/offset do círculo SVG (perímetro 100).
            "traco": round(fatia, 3),
            "resto": round(100 - fatia, 3),
            "offset": round(25 - acumulado, 3),
            "cor": cores[i % len(cores)],
        })
        acumulado += fatia

    if len(linhas) > limite:
        sobra = sum((linha["total"] for linha in linhas[limite:]), ZERO)
        fatia = float(sobra / total) * 100 if total else 0.0
        fatias.append({
            "nome": "Outras categorias",
            "valor": _dinheiro(sobra),
            "itens": sum(linha["itens"] for linha in linhas[limite:]),
            "percentual": round(fatia, 1),
            "traco": round(fatia, 3),
            "resto": round(100 - fatia, 3),
            "offset": round(25 - acumulado, 3),
            "cor": "#7186a2",
        })

    return {"fatias": fatias, "total": _dinheiro(total)}


def variacao(atual, anterior):
    """Variação percentual entre dois meses, pronta para o selo do card."""
    if anterior is None or anterior == 0:
        return None
    return round(float((atual - anterior) / anterior) * 100, 1)


def indicadores(serie):
    """Números grandes do topo da tela financeira."""
    receita_total = sum((linha["receita"] for linha in serie), ZERO)
    saida_total = sum((linha["saida"] for linha in serie), ZERO)
    lucro_total = receita_total - saida_total

    mes_atual = serie[-1] if serie else None
    mes_anterior = serie[-2] if len(serie) > 1 else None

    capital = EstoqueMaterial.objects.aggregate(
        total=Coalesce(
            Sum(
                F("quantidade") * F("preco_fornecedor"),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            ),
            Value(ZERO, output_field=DecimalField(max_digits=14, decimal_places=2)),
        )
    )["total"]

    margem = (
        round(float(lucro_total / receita_total) * 100, 1)
        if receita_total > 0 else None
    )

    return {
        "receita_total": _dinheiro(receita_total),
        "saida_total": _dinheiro(saida_total),
        "lucro_total": _dinheiro(lucro_total),
        "margem": margem,
        "capital_estoque": _dinheiro(capital),
        "receita_mes": mes_atual["receita"] if mes_atual else ZERO,
        "saida_mes": mes_atual["saida"] if mes_atual else ZERO,
        "lucro_mes": mes_atual["lucro"] if mes_atual else ZERO,
        "variacao_receita": variacao(
            mes_atual["receita"] if mes_atual else ZERO,
            mes_anterior["receita"] if mes_anterior else None,
        ),
        "variacao_saida": variacao(
            mes_atual["saida"] if mes_atual else ZERO,
            mes_anterior["saida"] if mes_anterior else None,
        ),
        "ticket_medio": _ticket_medio(serie),
    }


def _ticket_medio(serie):
    inicio = serie[0]["mes"] if serie else timezone.localdate()

    resumo = Venda.objects.filter(
        confirmado=True, criacao__date__gte=inicio,
    ).aggregate(
        total=Coalesce(
            Sum("valor_pago"),
            Value(ZERO, output_field=DecimalField(max_digits=14, decimal_places=2)),
        ),
        vendas=Count("id"),
    )

    if not resumo["vendas"]:
        return ZERO

    return _dinheiro(resumo["total"] / resumo["vendas"])


def funil_de_orcamentos(inicio):
    """Quanto foi proposto, aprovado e perdido no período."""
    linhas = (
        Orcamento.objects
        .filter(criacao__date__gte=inicio)
        .values("status")
        .annotate(itens=Count("id"))
    )

    contagem = {linha["status"]: linha["itens"] for linha in linhas}

    return {
        "rascunho": contagem.get(Orcamento.Status.RASCUNHO, 0),
        "enviado": contagem.get(Orcamento.Status.ENVIADO, 0),
        "aprovado": contagem.get(Orcamento.Status.APROVADO, 0),
        "recusado": contagem.get(Orcamento.Status.RECUSADO, 0),
        "total": sum(contagem.values()),
    }


def orcamentos_por_origem(inicio):
    """Compara a equipe interna e o vendedor ambulante sem consultas N+1."""
    resumo = {
        valor: {
            "codigo": valor,
            "rotulo": rotulo,
            "total": 0,
            "aprovados": 0,
            "valor_aprovado": ZERO,
        }
        for valor, rotulo in Orcamento.Origem.choices
    }

    orcamentos = (
        Orcamento.objects
        .filter(criacao__date__gte=inicio)
        .prefetch_related("itens")
    )
    for orcamento in orcamentos:
        linha = resumo.get(orcamento.origem)
        if linha is None:
            continue
        linha["total"] += 1
        if orcamento.status == Orcamento.Status.APROVADO:
            linha["aprovados"] += 1
            linha["valor_aprovado"] += orcamento.total

    for linha in resumo.values():
        linha["valor_aprovado"] = _dinheiro(linha["valor_aprovado"])
        linha["conversao"] = round(
            linha["aprovados"] / linha["total"] * 100,
            1,
        ) if linha["total"] else 0.0

    return list(resumo.values())
