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


# ======================================================================
# VALOR POR EXTENSO — o que transforma um número num recibo
# ======================================================================
#
# Recibo com o valor só em algarismos é recibo pela metade: a quantia
# escrita por extenso é o que impede que um "1.500,00" vire "11.500,00"
# com uma canetada, e é o que qualquer contador espera encontrar num
# comprovante de pagamento. Por isso mora aqui, ao lado de `dinheiro`:
# os dois dizem o MESMO valor, um para o olho e outro para a leitura em
# voz alta, e nenhum documento deve escolher sozinho como escrever.

_UNIDADES = (
    "", "um", "dois", "três", "quatro", "cinco", "seis", "sete", "oito", "nove",
)
_DEZ_A_DEZENOVE = (
    "dez", "onze", "doze", "treze", "quatorze",
    "quinze", "dezesseis", "dezessete", "dezoito", "dezenove",
)
_DEZENAS = (
    "", "", "vinte", "trinta", "quarenta",
    "cinquenta", "sessenta", "setenta", "oitenta", "noventa",
)
_CENTENAS = (
    "", "cento", "duzentos", "trezentos", "quatrocentos",
    "quinhentos", "seiscentos", "setecentos", "oitocentos", "novecentos",
)
#: Cada grupo de três casas, do menor para o maior, no singular e no plural.
_ESCALAS = (
    ("", ""),
    ("mil", "mil"),
    ("milhão", "milhões"),
    ("bilhão", "bilhões"),
    ("trilhão", "trilhões"),
)


def _grupo_por_extenso(numero):
    """1 a 999 escrito como se lê. Fora dessa faixa, string vazia."""
    if not 0 < numero < 1000:
        return ""
    if numero == 100:
        # "cem" só quando é exatamente cem; 101 é "cento e um".
        return "cem"

    partes = []
    centena, resto = divmod(numero, 100)
    if centena:
        partes.append(_CENTENAS[centena])
    if 10 <= resto <= 19:
        partes.append(_DEZ_A_DEZENOVE[resto - 10])
    else:
        dezena, unidade = divmod(resto, 10)
        if dezena:
            partes.append(_DEZENAS[dezena])
        if unidade:
            partes.append(_UNIDADES[unidade])
    return " e ".join(partes)


def _inteiro_por_extenso(numero):
    """O número inteiro em palavras, com as escalas e o "e" no lugar certo."""
    if numero == 0:
        return "zero"

    # Os grupos de três casas, do maior para o menor, junto da escala.
    grupos = []
    posicao = 0
    while numero > 0 and posicao < len(_ESCALAS):
        numero, grupo = divmod(numero, 1000)
        if grupo:
            grupos.append((grupo, posicao))
        posicao += 1
    if numero > 0:
        # Passou de trilhão: nenhum documento desta casa chega aqui, e
        # inventar palavra seria pior do que devolver vazio.
        return ""
    grupos.reverse()

    escritos = []
    for grupo, posicao in grupos:
        singular, plural = _ESCALAS[posicao]
        if posicao == 1 and grupo == 1:
            # "mil", e nunca "um mil".
            escritos.append("mil")
            continue
        texto = _grupo_por_extenso(grupo)
        if singular:
            texto = f"{texto} {singular if grupo == 1 else plural}"
        escritos.append(texto.strip())

    # O "E" ANTES DO ÚLTIMO GRUPO NÃO É ENFEITE.
    #
    # "mil e quinhentos" e "mil, quinhentos e vinte" são as duas formas
    # corretas: entra "e" quando o último grupo é menor que cem ou é uma
    # centena redonda; nos demais casos entra a vírgula, senão sai
    # "mil e quinhentos e vinte", que ninguém escreve.
    if len(escritos) == 1:
        return escritos[0]
    ultimo_valor = grupos[-1][0]
    ligacao = " e " if (ultimo_valor < 100 or ultimo_valor % 100 == 0) else ", "
    return ", ".join(escritos[:-1]) + ligacao + escritos[-1]


def _pede_a_preposicao(inteiros):
    """"Um milhão DE reais", mas "um milhão e quinhentos mil reais".

    A preposição entra quando o número termina em milhão, bilhão ou
    trilhão redondo -- e some assim que vem qualquer grupo depois. Sem
    esta conta o recibo saía com "dois milhões reais", que é justamente
    o tipo de erro que faz alguém desconfiar do documento inteiro.
    """
    if inteiros < 1_000_000:
        return False
    posicao = 0
    while inteiros and inteiros % 1000 == 0:
        inteiros //= 1000
        posicao += 1
    return posicao >= 2


def por_extenso(valor, moeda_singular="real", moeda_plural="reais"):
    """1250.5 -> 'mil, duzentos e cinquenta reais e cinquenta centavos'.

    Vazio para o que não é número: um recibo prefere não escrever nada a
    escrever "zero reais" no lugar de um valor que ninguém informou.
    """
    numero = para_decimal(valor)
    if numero is None:
        return ""

    numero = abs(numero).quantize(Decimal("0.01"))
    inteiros = int(numero)
    centavos = int((numero - inteiros) * 100)

    partes = []
    if inteiros or not centavos:
        escrito = _inteiro_por_extenso(inteiros)
        if not escrito:
            return ""
        unidade = moeda_singular if inteiros == 1 else moeda_plural
        if _pede_a_preposicao(inteiros):
            unidade = f"de {unidade}"
        partes.append(f"{escrito} {unidade}")
    if centavos:
        escrito = _inteiro_por_extenso(centavos)
        unidade = "centavo" if centavos == 1 else "centavos"
        partes.append(f"{escrito} {unidade}")
    return " e ".join(partes)
