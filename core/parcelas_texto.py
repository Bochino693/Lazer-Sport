"""O parcelamento escrito nas promoções nunca promete mais do que o cartão aceita.

A regra do checkout e do Mercado Pago (checkout.parcelas_maximas, LEIA-ME
seção 90 e o "Parcelado vendedor" da conta): uma parcela sem juros a cada
R$ 1.000,00, até 6x. As artes e as condições da Black Friday de 2026 diziam
"Em até 10x sem juros" -- e o cliente chegava no pagamento e via 6x (ou
menos). O dono decidiu: "tudo em 6x".

`condicao_em_6x` reescreve UMA linha que fala de parcelas acima do que a
regra deixa, com o número certo e o valor da parcela; o resto do texto fica
como está. É usada na exibição (Promocoes.lista_condicoes), no cadastro da
Black Friday e na migração 0195, que acerta o que já estava gravado.

Sem importar modelos de propósito: a migração usa isto também.
"""

import re
from decimal import Decimal, InvalidOperation

PARCELAS_NO_MAXIMO = 6
VALOR_POR_PARCELA = Decimal("1000.00")

# "10x", "10 x", "12X" -- o número de parcelas escrito na frase.
_PARCELAS = re.compile(r"(?<![\d,.])(\d{1,2})\s*[xX](?![a-zA-Z])")


def _decimal(valor):
    if valor in (None, ""):
        return None
    try:
        numero = Decimal(str(valor))
    except (InvalidOperation, ValueError):
        return None
    return numero if numero > 0 else None


def maximo_de_parcelas(preco):
    preco = _decimal(preco)
    if preco is None:
        return PARCELAS_NO_MAXIMO
    return max(1, min(PARCELAS_NO_MAXIMO, int(preco // VALOR_POR_PARCELA)))


def reais(valor):
    texto = f"{Decimal(valor).quantize(Decimal('0.01')):,.2f}"
    return "R$ " + texto.replace(",", "_").replace(".", ",").replace("_", ".")


def condicao_em_6x(linha, preco=None):
    """A linha com o parcelamento certo, ou a própria linha se já estava certa."""
    achado = _PARCELAS.search(linha or "")
    if not achado:
        return linha
    preco = _decimal(preco)
    maximo = maximo_de_parcelas(preco)
    if int(achado.group(1)) <= maximo:
        return linha

    no_cartao = "cartão" in linha.lower()
    if preco is None:
        return "Parcelamos em até 6x sem juros no cartão (uma parcela a cada R$ 1.000)"
    if maximo == 1:
        return "Pagamento à vista no PIX ou no cartão"
    parcela = reais(preco / maximo)
    if no_cartao:
        return f"Ou em até {maximo}x de {parcela} sem juros no cartão"
    return f"Em até {maximo}x sem juros de {parcela}"


def condicoes_em_6x(texto, preco=None):
    """Todas as linhas de um campo de condições (texto com quebras de linha)."""
    linhas = (texto or "").splitlines()
    return "\n".join(condicao_em_6x(linha, preco) for linha in linhas)
