"""O parcelamento escrito nas promoções nunca promete diferente do que o cartão cobra.

A regra do site (LEIA-ME seção 98; checkout.valor_no_cartao e
checkout.parcelas_maximas): no Pix, o preço; no cartão de crédito, o preço +
12%, em até 10x sem juros (parcela mínima de R$ 5). Antes (seção 94) era "uma
parcela a cada R$ 1.000, até 6x"; antes disso as artes diziam 10x sobre o preço
do Pix. O dono, agora: "todo site deve cobrir 10x sem juros e no crédito, em até
10x, o valor deve ser 12% a mais".

`condicao_em_6x` (o nome ficou: a migração 0195 usa) reescreve UMA linha que fala
de parcelas -- qualquer número de vezes, de qualquer regra antiga -- com o texto
certo: "Em até 10x de R$ 3.580,64 sem juros no cartão". O resto fica. É usada na
exibição (Promocoes.lista_condicoes), no cadastro da Black Friday e nas migrações
0195 e 0199, que acertam o que já estava gravado.

Sem importar modelos de propósito: as migrações usam isto também.
"""

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

ACRESCIMO_CARTAO = Decimal("0.12")
PARCELAS_NO_MAXIMO = 10
PARCELA_MINIMA = Decimal("5.00")

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


def no_cartao(preco):
    preco = _decimal(preco)
    if preco is None:
        return None
    return (preco * (1 + ACRESCIMO_CARTAO)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def maximo_de_parcelas(preco):
    """Em até quantas vezes o preço (do Pix) sai no cartão."""
    cartao = no_cartao(preco)
    if cartao is None:
        return PARCELAS_NO_MAXIMO
    return max(1, min(PARCELAS_NO_MAXIMO, int(cartao // PARCELA_MINIMA)))


def reais(valor):
    texto = f"{Decimal(valor).quantize(Decimal('0.01')):,.2f}"
    return "R$ " + texto.replace(",", "_").replace(".", ",").replace("_", ".")


def e_linha_de_parcelas(linha):
    return bool(_PARCELAS.search(linha or ""))


def e_linha_do_pagamento(linha):
    """A linha só repete o preço: o parcelamento ou o "à vista no Pix"."""
    return e_linha_de_parcelas(linha) or bool(_PIX.search(linha or ""))


def condicao_em_6x(linha, preco=None):
    """A linha com o parcelamento da regra do site, ou a própria linha se não fala de parcelas."""
    if not e_linha_de_parcelas(linha):
        return linha
    preco = _decimal(preco)
    if preco is None:
        return "Parcelamos em até 10x sem juros no cartão"
    vezes = maximo_de_parcelas(preco)
    cartao = no_cartao(preco)
    comeco = "Ou em até" if linha.strip().lower().startswith("ou") else "Em até"
    if vezes == 1:
        return f"{'Ou ' if comeco.startswith('Ou') else ''}{reais(cartao)} à vista no cartão"
    parcela = reais((cartao / vezes).quantize(Decimal("0.01")))
    return f"{comeco} {vezes}x de {parcela} sem juros no cartão"


def condicoes_em_6x(texto, preco=None):
    """Todas as linhas de um campo de condições (texto com quebras de linha)."""
    linhas = (texto or "").splitlines()
    return "\n".join(condicao_em_6x(linha, preco) for linha in linhas)
