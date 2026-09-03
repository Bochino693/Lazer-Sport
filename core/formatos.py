"""Como número vira texto na Lazer & Sport -- num lugar só.

POR QUE ISTO EXISTE. O mesmo valor aparecia de três jeitos na mesma
tela: "R$ 1250.00" na lista, "R$ 1.250,00" na proposta e "1250,0" no
resumo. Não é preciosismo -- preço escrito com ponto decimal é lido como
milhar por quem trabalha em português, e uma medida "2.00m" no papel do
cliente parece o começo de outro número.

A causa era não haver onde formatar: cada template resolvia sozinho, com
`floatformat`, com `|moeda`, ou com nada. Aqui ficam as duas regras da
casa -- dinheiro e medida --, e os filtros de template (`interno_extras`)
apenas as chamam.

DINHEIRO tem sempre duas casas. MEDIDA não: "2 m" é mais legível que
"2,00 m", e "2,5 m" mais que "2,50 m" -- então os zeros à direita caem,
que é como se fala e como se escreve na fita métrica.
"""

from decimal import Decimal, InvalidOperation

from django.utils.formats import number_format


def para_decimal(valor):
    """Aceita Decimal, float, int e string; devolve None no que não é número."""
    if valor is None or valor == "":
        return None
    if isinstance(valor, Decimal):
        return valor
    try:
        return Decimal(str(valor).strip().replace(" ", ""))
    except (InvalidOperation, ValueError, TypeError):
        return None


def dinheiro(valor, prefixo=""):
    """1234567.8 -> '1.234.567,80' (ou 'R$ 1.234.567,80' com prefixo)."""
    numero = para_decimal(valor)
    if numero is None:
        numero = Decimal("0")

    texto = number_format(
        numero.quantize(Decimal("0.01")),
        decimal_pos=2,
        force_grouping=True,
    )
    return f"{prefixo} {texto}".strip() if prefixo else texto


def medida(valor, unidade="m", casas=2):
    """2.00 -> '2 m'; 2.50 -> '2,5 m'; 0.375 -> '0,38 m'.

    Vazio devolve string vazia, e não "0 m": medida que ninguém informou
    não é medida zero, e escrever zero no papel do cliente afirma uma
    coisa que o cadastro não sabe.
    """
    numero = para_decimal(valor)
    if numero is None:
        return ""

    numero = numero.quantize(Decimal("1." + "0" * casas))
    # normalize() tira os zeros à direita; o quantize logo depois desfaz
    # a notação científica que ele produz em números redondos (2E+1).
    limpo = numero.normalize()
    if limpo == limpo.to_integral_value():
        limpo = limpo.quantize(Decimal("1"))

    texto = number_format(limpo, force_grouping=True)
    return f"{texto} {unidade}".strip() if unidade else texto


def dimensoes(altura, largura, profundidade, unidade="m"):
    """A ficha de tamanho como ela é lida em voz alta.

    Devolve vazio se faltar qualquer uma das três: meia medida no papel
    ("Altura 2 m x Largura —") vale menos que nenhuma, porque quem lê
    tem de perguntar de qualquer jeito.
    """
    partes = [medida(v, unidade) for v in (altura, largura, profundidade)]
    if not all(partes):
        return ""
    return (
        f"Altura {partes[0]} × Largura {partes[1]} × Profundidade {partes[2]}"
    )
