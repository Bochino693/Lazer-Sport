"""OS CRITÉRIOS DE ORDEM DA LISTA DE MONTAGEM (LEIA-ME-V10, seção 142).

O pedido do dono: "na listagem de montagem, você pode pôr filtros para ter
a lista e visualizar qual melhor se enquadra, por metros cúbicos, que já
está, um que seria a média de todos, outro para soltar compras menores,
soltar compras maiores, soltar pedidos maiores e pedidos menores entre
outras boas de ciência de dados que você pode pôr, default é a mediana."

A FILA OFICIAL NÃO MUDA AQUI. Quem entra em montagem quando abre uma vaga
continua sendo decidido pela posição gravada (`UnidadeMontagem.posicao`,
as setas da tela, `montagem.distribuir`). Este módulo só REORDENA A VISÃO
da fila, para a Engenharia de produção comparar "e se eu soltasse nesta
ordem?" -- não grava nada.

O QUE CADA MÁQUINA DA FILA TEM PARA MEDIR (só o que o sistema já sabe):

  * m3       -- o volume do brinquedo (altura x largura x profundidade);
  * compra   -- o VALOR da compra de onde ela veio (o total do pedido do
                site ou do orçamento);
  * pedido   -- o TAMANHO do pedido: quantas máquinas dele ainda estão na
                lista de montagem (não é o valor);
  * espera   -- há quantos dias ela chegou (o pagamento do pedido, a
                aprovação do orçamento);
  * prazo    -- quantos dias faltam para a data prometida (o fim da
                previsão; negativo = já passou);
  * trabalho -- os dias úteis de montagem dela;
  * valor_m3 -- o valor da compra dividido pelos m³ do pedido (o retorno
                por espaço de galpão).

AS DUAS NOTAS COMBINADAS. Para juntar medidas de unidades diferentes (m³,
reais, dias) cada máquina ganha, em cada medida, a POSIÇÃO dela de 0 a 100
(0 = sairia primeiro por aquela medida, 100 = por último; empate divide a
posição). As medidas e o lado que sai primeiro estão em `COMPONENTES`.

  * "media"   -- a MÉDIA das posições: o equilíbrio de todos os critérios,
                 em que uma medida muito fora puxa a nota;
  * "mediana" -- a MEDIANA das posições (o padrão): a posição "do meio" da
                 máquina entre os critérios. Uma única medida fora da curva
                 (uma compra enorme, um brinquedo gigante) não decide
                 sozinha: a máquina sobe quando a MAIORIA dos critérios
                 concorda que ela deve sair cedo.

Quem não tem o dado de um critério (brinquedo sem medida, por exemplo) vai
para o FIM da lista daquele critério, marcado; nas notas combinadas a
medida que falta é deixada de fora da conta daquela máquina.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from statistics import median

from django.utils import timezone

#: O critério que vem escolhido ao abrir a tela ("default é a mediana").
PADRAO = "mediana"


@dataclass(frozen=True)
class Criterio:
    chave: str
    rotulo: str
    icone: str
    grupo: str
    medida: str  # a medida que ele ordena ("" para a fila oficial e as notas)
    maior_primeiro: bool
    explica: str  # uma frase, para a tela


CRITERIOS = (
    Criterio("mediana", "Equilíbrio (mediana)", "bi-bullseye", "Equilíbrio", "", False,
             "A posição do meio de cada máquina entre todos os critérios: sai primeiro quem a maioria deles "
             "manda sair cedo. Um número fora da curva não decide sozinho."),
    Criterio("media", "Média de todos", "bi-calculator", "Equilíbrio", "", False,
             "A média das posições de cada máquina em todos os critérios."),
    Criterio("fila", "Fila oficial", "bi-list-ol", "Equilíbrio", "", False,
             "A ordem gravada, a que vale quando abre uma vaga. As setas mudam esta ordem."),
    Criterio("m3_menor", "Menor m³", "bi-box", "Tamanho", "m3", False,
             "As máquinas menores primeiro: ocupam menos galpão."),
    Criterio("m3_maior", "Maior m³", "bi-box-seam", "Tamanho", "m3", True,
             "As máquinas maiores primeiro: tira logo do caminho o que ocupa mais."),
    Criterio("pedido_menor", "Pedidos menores", "bi-bag", "Tamanho", "pedido", False,
             "Primeiro os pedidos com menos máquinas para montar: fecham mais pedidos em menos tempo."),
    Criterio("pedido_maior", "Pedidos maiores", "bi-bag-plus", "Tamanho", "pedido", True,
             "Primeiro os pedidos com mais máquinas para montar."),
    Criterio("compra_menor", "Compras menores", "bi-cash", "Valor", "compra", False,
             "Primeiro as compras de menor valor."),
    Criterio("compra_maior", "Compras maiores", "bi-cash-stack", "Valor", "compra", True,
             "Primeiro as compras de maior valor."),
    Criterio("valor_m3", "Mais valor por m³", "bi-graph-up-arrow", "Valor", "valor_m3", True,
             "Primeiro o que rende mais reais por metro cúbico de galpão."),
    Criterio("espera", "Mais antigo", "bi-hourglass-split", "Tempo", "espera", True,
             "Primeiro quem espera há mais tempo (pela data em que chegou)."),
    Criterio("prazo", "Prazo mais próximo", "bi-calendar-event", "Tempo", "prazo", False,
             "Primeiro quem tem a data prometida mais perto (ou já vencida)."),
    Criterio("trabalho", "Montagem mais curta", "bi-lightning-charge", "Tempo", "trabalho", False,
             "Primeiro o que monta em menos dias: libera a vaga mais rápido."),
)
POR_CHAVE = {criterio.chave: criterio for criterio in CRITERIOS}

#: As medidas que entram nas notas combinadas e o lado que SAI PRIMEIRO em
#: cada uma (True = o maior valor sai primeiro). É a leitura "o que solta a
#: produção mais depressa e sem deixar ninguém esquecido": o mais antigo, o
#: prazo mais próximo, a montagem mais curta, o menor volume, o pedido com
#: menos máquinas (fecha logo) e a compra de maior valor.
COMPONENTES = (
    ("espera", True),
    ("prazo", False),
    ("trabalho", False),
    ("m3", False),
    ("pedido", False),
    ("compra", True),
)
NOME_DA_MEDIDA = {
    "espera": "espera", "prazo": "prazo", "trabalho": "montagem", "m3": "m³",
    "pedido": "tamanho do pedido", "compra": "valor da compra", "valor_m3": "valor por m³",
}


def criterio(chave) -> Criterio:
    """O critério pedido na URL, ou o padrão (a mediana) quando não existe."""
    return POR_CHAVE.get((chave or "").strip(), POR_CHAVE[PADRAO])


# ----------------------------------------------------------------------
# AS MEDIDAS DE CADA MÁQUINA
# ----------------------------------------------------------------------
def valor_da_origem(producao):
    """O total da compra: do pedido do site ou do orçamento. None sem valor."""
    try:
        if producao.pedido_id:
            pedido = producao.pedido
            valor = pedido.valor_cobrado if pedido.valor_cobrado is not None else (
                pedido.total_final or pedido.total_liquido
            )
        else:
            valor = producao.orcamento.total
    except Exception:  # um valor que não se calcula não derruba a lista
        return None
    if valor is None:
        return None
    valor = float(valor)
    return valor if valor > 0 else None


def medir(unidades, *, todas=None, hoje=None, agora=None) -> dict:
    """{pk: {medida: número ou None}} das unidades, sem ir ao banco.

    `todas` são as unidades ativas da lista (para contar o tamanho e os m³
    de cada pedido); sem ela, vale o que veio em `unidades`. Quem chama já
    trouxe o brinquedo, o pedido e o orçamento (com os itens) de uma vez.
    """
    hoje = hoje or timezone.localdate()
    agora = agora or timezone.now()
    por_pedido, m3_do_pedido, valores = {}, {}, {}
    for unidade in (todas if todas is not None else unidades):
        por_pedido[unidade.producao_id] = por_pedido.get(unidade.producao_id, 0) + 1
        volume = getattr(unidade.brinquedo, "metros_cubicos", None) if unidade.brinquedo_id else None
        if volume:
            m3_do_pedido[unidade.producao_id] = m3_do_pedido.get(unidade.producao_id, 0.0) + float(volume)
    medidas = {}
    for unidade in unidades:
        if unidade.producao_id not in valores:
            valores[unidade.producao_id] = valor_da_origem(unidade.producao)
        compra = valores[unidade.producao_id]
        volume = getattr(unidade.brinquedo, "metros_cubicos", None) if unidade.brinquedo_id else None
        volume = float(volume) if volume else None
        m3_total = m3_do_pedido.get(unidade.producao_id)
        medidas[unidade.pk] = {
            "m3": volume,
            "compra": compra,
            "pedido": por_pedido.get(unidade.producao_id, 1),
            "espera": max((agora - unidade.chegada).days, 0) if unidade.chegada else None,
            "prazo": (unidade.previsao_ate - hoje).days if unidade.previsao_ate else None,
            "trabalho": unidade.dias or None,
            "valor_m3": (compra / m3_total) if compra and m3_total else None,
        }
    return medidas


# ----------------------------------------------------------------------
# AS CONTAS
# ----------------------------------------------------------------------
def posicoes(valores: dict, maior_primeiro: bool) -> dict:
    """{chave: 0..100} entre quem TEM o dado (0 = sai primeiro). Empate divide a posição."""
    com_dado = sorted(
        ((valor, chave) for chave, valor in valores.items() if valor is not None),
        key=lambda par: par[0], reverse=maior_primeiro,
    )
    quantos = len(com_dado)
    if not quantos:
        return {}
    if quantos == 1:
        return {com_dado[0][1]: 0.0}
    resultado, indice = {}, 0
    while indice < quantos:
        fim = indice
        while fim + 1 < quantos and com_dado[fim + 1][0] == com_dado[indice][0]:
            fim += 1
        posicao = ((indice + fim) / 2) / (quantos - 1) * 100
        for _, chave in com_dado[indice:fim + 1]:
            resultado[chave] = posicao
        indice = fim + 1
    return resultado


def notas(medidas: dict, combinar) -> dict:
    """{pk: nota 0..100} juntando as posições de `COMPONENTES` com `combinar` (média ou mediana)."""
    por_medida = {
        medida: posicoes({pk: valores.get(medida) for pk, valores in medidas.items()}, maior)
        for medida, maior in COMPONENTES
    }
    resultado = {}
    for pk in medidas:
        dela = [por_medida[medida][pk] for medida, _ in COMPONENTES if pk in por_medida[medida]]
        resultado[pk] = combinar(dela) if dela else None
    return resultado


def _media(numeros):
    return sum(numeros) / len(numeros)


def desempate(unidade):
    """A ordem oficial: é ela que desempata, sempre do mesmo jeito."""
    return (
        unidade.posicao if unidade.posicao is not None else 10 ** 9,
        unidade.chegada,
        unidade.pk or 0,
    )


def _reais(valor) -> str:
    inteiro = f"{Decimal(str(valor)).quantize(Decimal('0.01')):,.2f}"
    return "R$ " + inteiro.replace(",", "X").replace(".", ",").replace("X", ".")


def _numero(valor, casas=2) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


def escrever(medida, valor) -> str:
    """O número do critério, como aparece ao lado da máquina."""
    if valor is None:
        return ""
    if medida == "m3":
        return f"{_numero(valor)} m³"
    if medida == "compra":
        return _reais(valor)
    if medida == "valor_m3":
        return f"{_reais(valor)} por m³"
    if medida == "pedido":
        return f"{int(valor)} máquina{'s' if int(valor) != 1 else ''} no pedido"
    if medida == "espera":
        return f"{int(valor)} dia{'s' if int(valor) != 1 else ''} esperando"
    if medida == "trabalho":
        return f"{int(valor)} dia{'s' if int(valor) != 1 else ''} úteis de montagem"
    if medida == "prazo":
        dias = int(valor)
        if dias < 0:
            return f"prazo vencido há {-dias} dia{'s' if dias != -1 else ''}"
        if dias == 0:
            return "prazo vence hoje"
        return f"faltam {dias} dia{'s' if dias != 1 else ''}"
    if medida == "nota":
        return f"nota {_numero(valor, 0)}"
    return _numero(valor)


def _resumir(medida, valor) -> str:
    """O número do resumo (média e mediana), curto."""
    if medida == "m3":
        return f"{_numero(valor)} m³"
    if medida in ("compra", "valor_m3"):
        return _reais(valor)
    if medida == "nota":
        return _numero(valor, 0)
    if medida == "pedido":
        return f"{_numero(valor, 1)} máq."
    return f"{_numero(valor, 1)} dias"


@dataclass
class Resumo:
    criterio: Criterio
    total: int
    com_dado: int
    sem_dado: int
    media: str
    mediana: str
    soma: str
    medida: str


def ordenar(unidades, chave=PADRAO, *, todas=None, hoje=None, agora=None):
    """(as unidades na ordem do critério, o Resumo). Não grava nada.

    Cada unidade ganha `criterio_ordem` (1º, 2º...), `criterio_texto` (o
    número que o critério usou) e `criterio_sem_dado`.
    """
    escolhido = criterio(chave)
    unidades = list(unidades)
    if escolhido.chave == "fila":
        ordenadas = sorted(unidades, key=desempate)
        for ordem, unidade in enumerate(ordenadas, start=1):
            unidade.criterio_ordem, unidade.criterio_texto, unidade.criterio_sem_dado = ordem, "", False
        return ordenadas, Resumo(escolhido, len(ordenadas), len(ordenadas), 0, "", "", "", "")

    medidas = medir(unidades, todas=todas, hoje=hoje, agora=agora)
    if escolhido.medida:
        medida, maior_primeiro = escolhido.medida, escolhido.maior_primeiro
        valores = {pk: dela.get(medida) for pk, dela in medidas.items()}
    else:
        medida, maior_primeiro = "nota", False
        valores = notas(medidas, median if escolhido.chave == "mediana" else _media)

    def chave_da_ordem(unidade):
        valor = valores.get(unidade.pk)
        if valor is None:
            return (1, 0, desempate(unidade))  # sem o dado: no fim, na ordem oficial
        return (0, -valor if maior_primeiro else valor, desempate(unidade))

    ordenadas = sorted(unidades, key=chave_da_ordem)
    for ordem, unidade in enumerate(ordenadas, start=1):
        valor = valores.get(unidade.pk)
        unidade.criterio_ordem = ordem
        unidade.criterio_sem_dado = valor is None
        unidade.criterio_texto = escrever(medida, valor) if valor is not None else (
            "sem medida no cadastro" if medida in ("m3", "valor_m3") else "sem este dado"
        )
        if medida == "nota" and valor is not None:
            dela = medidas[unidade.pk]
            unidade.criterio_detalhe = " · ".join(
                escrever(nome, dela[nome]) for nome, _ in COMPONENTES if dela.get(nome) is not None
            )
    numeros = [valor for valor in valores.values() if valor is not None]
    return ordenadas, Resumo(
        criterio=escolhido,
        total=len(ordenadas),
        com_dado=len(numeros),
        sem_dado=len(ordenadas) - len(numeros),
        media=_resumir(medida, _media(numeros)) if numeros else "",
        mediana=_resumir(medida, median(numeros)) if numeros else "",
        soma=_resumir(medida, sum(numeros)) if numeros and medida in ("m3", "trabalho") else "",
        medida=NOME_DA_MEDIDA.get(medida, "nota de 0 a 100 (menor sai primeiro)"),
    )
