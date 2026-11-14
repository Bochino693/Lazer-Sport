"""O parcelamento do site: quantas vezes sem juros, os juros acima disso e o texto.

A regra (LEIA-ME seções 98 e 99):
  * no Pix, o preço cadastrado;
  * no cartão de crédito, o preço + 12% (ACRESCIMO_CARTAO), em até 10x;
  * SEM JUROS até um número de parcelas que é de cada objeto (o campo
    `parcelas_sem_juros` do brinquedo, da peça, do combo e da promoção). Vazio,
    vale o padrão: PROMOÇÕES em até 10x sem juros; brinquedos, peças e combos
    em até 6x sem juros. O dono: "com as promoções, mantenha os 10x sem juros;
    com os brinquedos normais, até 6x sem juros para o cliente, acima disso com
    juros, podendo manipular isso pelo objeto para as demais promoções";
  * ACIMA desse número, com juros: a tabela Price à taxa do mês
    (settings.JUROS_CARTAO_AO_MES, padrão 2,99%) sobre o valor do cartão;
  * cada parcela de pelo menos R$ 5,00 (o mínimo do Mercado Pago).

Quem cobra os juros é o SITE, não o Mercado Pago: lá o parcelamento fica todo
"sem juros" (o vendedor assume) até 10x, e o site manda o total certo de cada
número de parcelas. Assim cada objeto tem a sua regra, coisa que a conta do
Mercado Pago (um número só para tudo) não faz.

Num pedido com itens de regras diferentes (uma promoção e uma peça), cada item
paga os juros dele: o total no cartão é a soma das partes (`partes`: a parte do
total de cada item e as vezes sem juros dele).

`condicao_em_6x` (o nome ficou: as migrações 0195 e 0199 usam) reescreve UMA
linha das condições de uma promoção que fala de parcelas com o texto certo.

Sem importar modelos de propósito: as migrações usam isto também.
"""

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

ACRESCIMO_CARTAO = Decimal("0.12")
PARCELAS_NO_MAXIMO = 10
PARCELA_MINIMA = Decimal("5.00")
SEM_JUROS_PADRAO = 6        # brinquedos, peças e combos
SEM_JUROS_PROMOCAO = 10     # promoções
JUROS_AO_MES_PADRAO = Decimal("0.0299")

CENTAVO = Decimal("0.01")

# "10x", "10 x", "12X" -- o número de parcelas escrito na frase.
_PARCELAS = re.compile(r"(?<![\d,.])(\d{1,2})\s*[xX](?![a-zA-Z])")
# "no Pix", "à vista no PIX", "à vista com 7% de desconto" -- a linha do pagamento à vista:
# o bloco de preço (seção 98) já diz o preço do Pix, o único à vista do site.
_PIX = re.compile(r"\bpix\b|\b[àa] vista\b", re.IGNORECASE)


def _decimal(valor):
    if valor in (None, ""):
        return None
    try:
        numero = Decimal(str(valor))
    except (InvalidOperation, ValueError):
        return None
    return numero if numero > 0 else None


def _centavos(valor):
    return Decimal(valor).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def juros_ao_mes():
    """A taxa do mês acima das vezes sem juros (settings.JUROS_CARTAO_AO_MES, em %)."""
    try:
        from django.conf import settings

        taxa = getattr(settings, "JUROS_CARTAO_AO_MES", None)
    except Exception:  # noqa: BLE001 -- fora do Django, o padrão
        taxa = None
    try:
        taxa = Decimal(str(taxa).replace(",", ".")) if taxa not in (None, "") else None
    except (InvalidOperation, ValueError):
        taxa = None
    # 0 desliga os juros (tudo sem juros); vazio ou inválido, o padrão
    return (taxa / 100) if taxa is not None and taxa >= 0 else JUROS_AO_MES_PADRAO


# ----------------------------------------------------------------------
# Quantas vezes sem juros
# ----------------------------------------------------------------------
def normalizar_sem_juros(valor, padrao=SEM_JUROS_PADRAO):
    """De 1 a 10; vazio ou inválido, o padrão."""
    try:
        numero = int(valor)
    except (TypeError, ValueError):
        return padrao
    return max(1, min(PARCELAS_NO_MAXIMO, numero))


def padrao_do_tipo(tipo):
    """O padrão pelo tipo: "promocao"/"promocoes" (o model_name) é 10x; o resto, 6x."""
    return SEM_JUROS_PROMOCAO if str(tipo or "").lower().startswith("promoc") else SEM_JUROS_PADRAO


def sem_juros_do_objeto(objeto):
    """As vezes sem juros de um brinquedo, peça, combo ou promoção (o campo, ou o padrão)."""
    if objeto is None:
        return SEM_JUROS_PADRAO
    meta = getattr(objeto, "_meta", None)
    padrao = padrao_do_tipo(getattr(meta, "model_name", "") or type(objeto).__name__)
    return normalizar_sem_juros(getattr(objeto, "parcelas_sem_juros", None), padrao)


def ler_sem_juros(texto):
    """O campo do painel: "" (o padrão) ou de 1 a 10. Devolve None para o padrão."""
    texto = str(texto or "").strip().lower().rstrip("x").strip()
    if not texto or texto in ("padrao", "padrão"):
        return None
    try:
        numero = int(texto)
    except ValueError:
        raise ValueError("As parcelas sem juros vão de 1 a 10.")
    if not 1 <= numero <= PARCELAS_NO_MAXIMO:
        raise ValueError("As parcelas sem juros vão de 1 a 10.")
    return numero


# ----------------------------------------------------------------------
# O total no cartão
# ----------------------------------------------------------------------
def no_cartao(preco):
    """O preço no cartão sem juros: + 12%."""
    preco = _decimal(preco)
    if preco is None:
        return None
    return _centavos(preco * (1 + ACRESCIMO_CARTAO))


def fator_de_juros(parcelas, sem_juros, juros=None):
    """1 até as vezes sem juros; acima, o fator da tabela Price (total / valor)."""
    parcelas = max(1, int(parcelas))
    if parcelas <= sem_juros:
        return Decimal(1)
    i = juros_ao_mes() if juros is None else Decimal(juros)
    if i <= 0:
        return Decimal(1)
    return parcelas * i / (1 - 1 / (1 + i) ** parcelas)


def total_no_cartao(partes, parcelas, juros=None):
    """O total no cartão em `parcelas` vezes. `partes`: [(valor no Pix, vezes sem juros), ...]."""
    soma = Decimal(0)
    for valor, sem_juros in partes:
        valor = _decimal(valor)
        if valor is None:
            continue
        soma += valor * (1 + ACRESCIMO_CARTAO) * fator_de_juros(parcelas, sem_juros, juros)
    return _centavos(soma)


def opcoes_de_parcelas(partes, juros=None):
    """Cada número de parcelas possível: [{parcelas, total, parcela, sem_juros}, ...].

    Vai de 1x até 10x, enquanto a parcela der pelo menos R$ 5,00. `sem_juros` é
    verdadeiro quando nenhuma parte paga juros naquele número de vezes.
    """
    partes = [(v, normalizar_sem_juros(s)) for v, s in partes if _decimal(v) is not None]
    if not partes:
        return []
    opcoes = []
    a_vista = total_no_cartao(partes, 1, juros)
    for n in range(1, PARCELAS_NO_MAXIMO + 1):
        total = total_no_cartao(partes, n, juros)
        parcela = (total / n).quantize(CENTAVO, rounding=ROUND_HALF_UP)
        if n > 1 and parcela < PARCELA_MINIMA:
            break
        opcoes.append({
            "parcelas": n,
            "total": total,
            "parcela": parcela,
            # sem juros: o total é o mesmo do cartão à vista (taxa 0 também)
            "sem_juros": total == a_vista,
        })
    return opcoes


def resumo_do_cartao(preco, sem_juros=SEM_JUROS_PADRAO, juros=None):
    """O que o card diz de um objeto: o cartão, até quantas vezes sem juros e o máximo com juros."""
    preco = _decimal(preco)
    if preco is None:
        return None
    opcoes = opcoes_de_parcelas([(preco, sem_juros)], juros)
    livres = [o for o in opcoes if o["sem_juros"]]
    ultima_livre = livres[-1]
    ultima = opcoes[-1]
    return {
        "cartao": opcoes[0]["total"],
        "vezes": ultima_livre["parcelas"],
        "parcela": ultima_livre["parcela"],
        "vezes_com_juros": ultima["parcelas"] if not ultima["sem_juros"] else 0,
        "parcela_com_juros": ultima["parcela"] if not ultima["sem_juros"] else None,
        "total_com_juros": ultima["total"] if not ultima["sem_juros"] else None,
    }


def maximo_de_parcelas(preco, sem_juros=SEM_JUROS_PROMOCAO):
    """Em até quantas vezes SEM JUROS o preço (do Pix) sai no cartão."""
    resumo = resumo_do_cartao(preco, sem_juros)
    return resumo["vezes"] if resumo else normalizar_sem_juros(sem_juros)


# ----------------------------------------------------------------------
# O texto das condições das promoções
# ----------------------------------------------------------------------
def reais(valor):
    texto = f"{Decimal(valor).quantize(CENTAVO):,.2f}"
    return "R$ " + texto.replace(",", "_").replace(".", ",").replace("_", ".")


def e_linha_de_parcelas(linha):
    return bool(_PARCELAS.search(linha or ""))


def e_linha_do_pagamento(linha):
    """A linha só repete o preço: o parcelamento ou o "à vista no Pix"."""
    return e_linha_de_parcelas(linha) or bool(_PIX.search(linha or ""))


def condicao_em_6x(linha, preco=None, sem_juros=SEM_JUROS_PROMOCAO):
    """A linha com o parcelamento da regra do site, ou a própria linha se não fala de parcelas."""
    if not e_linha_de_parcelas(linha):
        return linha
    sem_juros = normalizar_sem_juros(sem_juros, SEM_JUROS_PROMOCAO)
    resumo = resumo_do_cartao(preco, sem_juros)
    if resumo is None:
        return f"Parcelamos em até {sem_juros}x sem juros no cartão"
    comeco = "Ou em até" if linha.strip().lower().startswith("ou") else "Em até"
    if resumo["vezes"] == 1:
        return f"{'Ou ' if comeco.startswith('Ou') else ''}{reais(resumo['cartao'])} à vista no cartão"
    return f"{comeco} {resumo['vezes']}x de {reais(resumo['parcela'])} sem juros no cartão"


def condicoes_em_6x(texto, preco=None, sem_juros=SEM_JUROS_PROMOCAO):
    """Todas as linhas de um campo de condições (texto com quebras de linha)."""
    linhas = (texto or "").splitlines()
    return "\n".join(condicao_em_6x(linha, preco, sem_juros) for linha in linhas)
