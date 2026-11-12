"""As análises gráficas das telas de gestão: quanto cada coisa rendeu, e quando.

UMA PERGUNTA, SEMPRE A MESMA FORMA. Para um tipo (brinquedo, promoção,
cupom, usuário...), opcionalmente um objeto só, e um período, a resposta
traz para cada métrica:
  * o total do período e o do PERÍODO ANTERIOR de mesmo tamanho (a mesma
    janela, recuada, até o mesmo ponto: "hoje até as 15h" contra "ontem até
    as 15h", e não contra o dia inteiro de ontem);
  * a série no tempo, nos baldes do período (ver PERIODOS);
  * a distribuição por dia da semana (exceto em Hoje);
  * no resumo do tipo, o ranking dos objetos que mais renderam.

COMO O BANCO É CONSULTADO. Cada FONTE é um queryset que já agrupa no banco,
no fuso do site (Trunc*/Extract* com tzinfo). As fontes aditivas (contagens
e somas) agregam por HORA em "Hoje" e por DIA nos demais períodos -- e
semanas e meses são a soma desses dias. Assim UMA consulta por fonte dá a
série atual, a do período anterior e o dia da semana, e várias métricas
saem juntas (visitas e carrinho da mesma tabela, pedidos e receita das
mesmas linhas). A fonte que conta pessoas distintas ("ativos") não pode ser
somada dia a dia -- quem veio segunda e terça é um ativo na semana, não
dois --, então agrupa direto na unidade do período (TruncWeek/TruncMonth).

SEM NÚMERO INVENTADO. Métrica sem nenhuma linha no banco vai como
`sem_dados`, e não como zero. As visitas e as idas ao carrinho só são
registradas por hora desde a seção 76 do LEIA-ME: a cobertura vai junto
(`desde`), e a comparação com um período anterior que o registro não cobre
sai como "sem base".

SEM PAREDE DE CAIXAS VAZIAS (o AJUSTE da seção 76). A métrica que não teve
nada no período NEM no anterior vai marcada `vazia`, com o `motivo` em
português de gente ("nenhum registro até hoje", "registrado desde 10/11:
nada neste período", "sem movimento neste período nem no anterior"): a tela
desenha cartão só para as que têm número e junta as vazias numa linha. A
`principal` da resposta é a primeira métrica que TEM dado -- o gráfico não
abre numa métrica vazia.

GRÁFICO QUE EXISTE. Quem conta pessoas distintas diz a `forma` "colunas"
(uma coluna por dia, semana ou mês: os baldes não se somam) e, em "Hoje",
sai hora a hora quando a fonte guarda a hora (as jogadas); a que só guarda
o dia (os acessos) manda as PESSOAS do dia, com o primeiro e o último sinal
de cada uma (`pessoas`), e a tela desenha a linha do tempo de quem esteve
ativo. Nenhuma resposta pede um gráfico que não dá para desenhar.

O resultado de cada pergunta fica DOIS MINUTOS no cache: o painel pede de
novo a cada troca de período, e a mesma tela aberta em três tablets não
precisa de três rodadas no banco.
"""

from __future__ import annotations

import calendar
import datetime as dt
import logging
from contextlib import contextmanager
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Callable

from django.core.cache import cache
from django.db import connection, transaction
from django.db.models import (
    Count,
    DateField,
    DateTimeField,
    DecimalField,
    F,
    Max,
    Min,
    Q,
    Sum,
)
from django.db.models.functions import Trunc
from django.utils import timezone

log = logging.getLogger(__name__)


@contextmanager
def _ponto_de_retorno():
    """A consulta que falhar não envenena as seguintes.

    Dentro de uma transação (os testes; uma view com transação) o banco recusa tudo depois
    de um erro, então a fonte roda num ponto de retorno. Fora dela -- o site, em autocommit
    -- cada consulta já é a sua transação: nada a mais vai ao banco (cada ida e volta ao
    banco remoto custa dezenas de milissegundos).
    """
    if connection.in_atomic_block:
        with transaction.atomic():
            yield
    else:
        yield

PERIODOS = {
    # código: (rótulo, dias na janela, balde)
    "hoje": ("Hoje", 1, "hora"),
    "semana": ("Semana", 7, "dia"),
    "mes": ("Mês", 30, "dia"),
    "trimestre": ("3 meses", 90, "semana"),
    "semestre": ("Semestre", 180, "semana"),
    "ano": ("Ano", 365, "mes"),
}
PERIODO_PADRAO = "mes"
#: O período personalizado ("Dias", de/até) aceita no máximo isto.
MAXIMO_DIAS = 731
CACHE_SEGUNDOS = 120
RANKING_TAMANHO = 8
#: A cor do quadradinho do ícone de cada indicador: sai da ORDEM em que o
#: tipo declara as métricas (a mesma no painel e na ficha), nunca do valor.
#: Verde e vermelho ficam de fora (são da variação), e o laranja também: é
#: a cor da série e da escolha.
TONS = ("magenta", "violet", "info", "apoio")

MESES = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")
DIAS_DA_SEMANA = ("seg", "ter", "qua", "qui", "sex", "sáb", "dom")
DIAS_DA_SEMANA_LONGOS = ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo")

DINHEIRO = DecimalField(max_digits=14, decimal_places=2)


class PeriodoInvalido(ValueError):
    """O período pedido não existe ou as datas não fazem sentido."""


# ======================================================================
# JANELA DE TEMPO
# ======================================================================

def _fuso():
    return timezone.get_current_timezone()


def _meia_noite(dia):
    return timezone.make_aware(dt.datetime.combine(dia, dt.time.min), _fuso())


def _local_ingenuo(valor):
    """Qualquer data/hora do banco -> data/hora local sem fuso (a chave dos baldes)."""
    if valor is None:
        return None
    if isinstance(valor, dt.datetime):
        if timezone.is_aware(valor):
            valor = timezone.localtime(valor, _fuso())
        return valor.replace(tzinfo=None)
    return dt.datetime.combine(valor, dt.time.min)


def _somar_meses(dia, meses):
    mes = dia.month - 1 + meses
    ano = dia.year + mes // 12
    mes = mes % 12 + 1
    return dia.replace(year=ano, month=mes, day=min(dia.day, calendar.monthrange(ano, mes)[1]))


def balde_de(momento, unidade):
    """O começo do balde em que `momento` (local, sem fuso) cai."""
    if unidade == "hora":
        return momento.replace(minute=0, second=0, microsecond=0)
    dia = momento.replace(hour=0, minute=0, second=0, microsecond=0)
    if unidade == "dia":
        return dia
    if unidade == "semana":
        return dia - dt.timedelta(days=dia.weekday())
    return dia.replace(day=1)


@dataclass(frozen=True)
class Janela:
    codigo: str
    rotulo: str
    unidade: str
    inicio: dt.datetime        # com fuso, incluso
    fim: dt.datetime           # com fuso, excluso (agora, nos períodos ao vivo)
    duracao: dt.timedelta
    agora: dt.datetime
    de: dt.date | None = None
    ate: dt.date | None = None

    @property
    def anterior_inicio(self):
        return self.inicio - self.duracao

    @property
    def anterior_fim(self):
        return self.fim - self.duracao

    @property
    def dias(self):
        return self.duracao.days

    @property
    def ultimo_dia(self):
        return timezone.localtime(self.fim - dt.timedelta(microseconds=1), _fuso()).date()

    def filtro(self, campo, so_atual=False, campo_e_data=False):
        """O Q das duas janelas (atual e anterior), sem o vão entre elas."""
        if campo_e_data:
            atual = Q(**{f"{campo}__gte": timezone.localtime(self.inicio).date(), f"{campo}__lte": self.ultimo_dia})
            if so_atual:
                return atual
            fim_anterior = timezone.localtime(self.anterior_fim - dt.timedelta(microseconds=1)).date()
            return atual | Q(**{
                f"{campo}__gte": timezone.localtime(self.anterior_inicio).date(),
                f"{campo}__lte": fim_anterior,
            })
        atual = Q(**{f"{campo}__gte": self.inicio, f"{campo}__lt": self.fim})
        if so_atual:
            return atual
        return atual | Q(**{f"{campo}__gte": self.anterior_inicio, f"{campo}__lt": self.anterior_fim})

    def baldes(self):
        """Os começos de balde (local, sem fuso), do mais antigo ao mais novo."""
        inicio = _local_ingenuo(self.inicio)
        ultimo = self.ultimo_dia
        if self.unidade == "hora":
            atual = balde_de(inicio, "hora")
            fim = dt.datetime.combine(ultimo + dt.timedelta(days=1), dt.time.min)
            passo = lambda v: v + dt.timedelta(hours=1)  # noqa: E731
        else:
            atual = balde_de(inicio, self.unidade)
            fim = dt.datetime.combine(ultimo + dt.timedelta(days=1), dt.time.min)
            if self.unidade == "dia":
                passo = lambda v: v + dt.timedelta(days=1)  # noqa: E731
            elif self.unidade == "semana":
                passo = lambda v: v + dt.timedelta(days=7)  # noqa: E731
            else:
                passo = lambda v: _somar_meses(v, 1)  # noqa: E731
        baldes = []
        while atual < fim:
            baldes.append(atual)
            atual = passo(atual)
        return baldes

    def _intervalo(self, inicio, fim):
        """"14/10 a 12/11", com o ano quando ele muda no caminho ou não é o de hoje."""
        inicio = timezone.localtime(inicio)
        fim = timezone.localtime(fim)
        com_ano = inicio.year != fim.year or fim.year != timezone.localtime(self.agora).year
        formato = "%d/%m/%Y" if com_ano else "%d/%m"
        if inicio.date() == fim.date():
            return fim.strftime(formato)
        return f"{inicio.strftime(formato)} a {fim.strftime(formato)}"

    @property
    def ao_vivo(self):
        return self.fim >= self.agora - dt.timedelta(seconds=1)

    def textos(self):
        """{"titulo", "comparacao", "anterior_curto"}: a frase do período, sem jargão.

        "Hoje, 12/11, até 15:30" + "comparado com ontem até a mesma hora";
        "Últimos 30 dias (14/10 a 12/11)" + "comparado com os 30 dias
        anteriores (14/09 a 13/10)". `anterior_curto` é como cada cartão
        chama o período anterior ("ontem: 4", "antes: 4").
        """
        micro = dt.timedelta(microseconds=1)
        atual = self._intervalo(self.inicio, self.fim - micro)
        anterior = self._intervalo(self.anterior_inicio, self.anterior_fim - micro)
        if self.unidade == "hora" and self.dias == 1:
            dia = timezone.localtime(self.inicio)
            if self.ao_vivo and dia.date() == timezone.localtime(self.agora).date():
                ate = timezone.localtime(self.fim)
                return {
                    "titulo": f"Hoje, {dia:%d/%m}, até {ate:%H:%M}",
                    "comparacao": "comparado com ontem até a mesma hora",
                    "anterior_curto": "ontem",
                }
            return {
                "titulo": f"Dia {atual}",
                "comparacao": f"comparado com o dia anterior ({anterior})",
                "anterior_curto": "dia anterior",
            }
        dias = f"{self.dias} dias"
        if self.codigo == "dias":
            titulo = f"De {atual} ({dias})"
        else:
            titulo = f"Últimos {dias} ({atual})"
        return {
            "titulo": titulo,
            "comparacao": f"comparado com os {dias} anteriores ({anterior})",
            "anterior_curto": "antes",
        }

    def descricao(self):
        textos = self.textos()
        return f"{textos['titulo']} · {textos['comparacao']}"


def _data(valor):
    if isinstance(valor, dt.date):
        return valor
    try:
        return dt.date.fromisoformat(str(valor).strip())
    except (TypeError, ValueError):
        raise PeriodoInvalido("Use datas no formato AAAA-MM-DD.")


def janela(codigo=PERIODO_PADRAO, agora=None, de=None, ate=None):
    """A janela de um período; `agora` fixo nos testes."""
    agora = timezone.localtime(agora or timezone.now(), _fuso())
    hoje = agora.date()
    codigo = (codigo or PERIODO_PADRAO).strip().lower()

    if codigo == "dias":
        if not de or not ate:
            raise PeriodoInvalido("Escolha o primeiro e o último dia.")
        de, ate = _data(de), _data(ate)
        if ate < de:
            de, ate = ate, de
        if de > hoje:
            raise PeriodoInvalido("O período começa no futuro.")
        ate = min(ate, hoje)
        dias = (ate - de).days + 1
        if dias > MAXIMO_DIAS:
            raise PeriodoInvalido(f"Escolha no máximo {MAXIMO_DIAS} dias.")
        if dias == 1:
            unidade = "hora"
        elif dias <= 62:
            unidade = "dia"
        elif dias <= 200:
            unidade = "semana"
        else:
            unidade = "mes"
        inicio = _meia_noite(de)
        fim = min(_meia_noite(ate + dt.timedelta(days=1)), agora)
        rotulo = f"{de:%d/%m} a {ate:%d/%m}" if dias > 1 else f"{de:%d/%m/%Y}"
        return Janela("dias", rotulo, unidade, inicio, fim, dt.timedelta(days=dias), agora, de, ate)

    if codigo not in PERIODOS:
        raise PeriodoInvalido("Período desconhecido.")
    rotulo, dias, unidade = PERIODOS[codigo]
    inicio = _meia_noite(hoje - dt.timedelta(days=dias - 1))
    return Janela(codigo, rotulo, unidade, inicio, agora, dt.timedelta(days=dias), agora)


def rotulo_do_balde(balde, unidade, inicio_janela=None):
    """(curto, longo) para o eixo e para a dica do gráfico."""
    if unidade == "hora":
        return f"{balde:%H}h", f"{balde:%d/%m} das {balde:%H}h às {(balde + dt.timedelta(hours=1)):%H}h"
    if unidade == "dia":
        semana = DIAS_DA_SEMANA[balde.weekday()]
        return f"{balde:%d/%m}", f"{semana}, {balde:%d/%m/%Y}"
    if unidade == "semana":
        comeco = max(balde, inicio_janela) if inicio_janela else balde
        return f"{comeco:%d/%m}", f"semana de {comeco:%d/%m/%Y}"
    return f"{MESES[balde.month - 1]}/{balde:%y}", f"{MESES[balde.month - 1]} de {balde.year}"


# ======================================================================
# MÉTRICAS E FONTES
# ======================================================================

@dataclass(frozen=True)
class Metrica:
    codigo: str
    rotulo: str
    icone: str = "bi-graph-up"
    formato: str = "inteiro"     # "inteiro" ou "dinheiro"
    ajuda: str = ""
    #: True: subir é bom (verde); False: subir é ruim; None: neutro.
    subir_e_bom: bool | None = True
    #: só no resumo do tipo, ou só na análise de um objeto
    so_geral: bool = False
    so_objeto: bool = False
    #: métrica calculada: (numerador, denominador) -- ex. ticket médio
    razao: tuple[str, str] | None = None
    #: como o ranking escreve o valor ("12 dias"): (singular, plural)
    ranking_unidade: tuple[str, str] | None = None
    #: "colunas" para o que é contado balde a balde e não se liga com uma
    #: linha (os dias com acesso: em cada dia, apareceu ou não apareceu)
    forma: str = ""
    #: o título do gráfico por unidade, quando "<rótulo> por dia" soa torto
    #: ({"dia": "Em que dias apareceu"})
    titulos: dict | None = None


@dataclass(eq=False)
class Fonte:
    """Um queryset agrupado no banco que alimenta uma ou mais métricas.

    `metricas` liga (valor do separador ou None, apelido do agregado) ao
    código da métrica: a tabela de interações dá visitas E carrinho pelo
    campo `evento`; as linhas de pedido dão pedidos E receita.
    """

    chave: str
    consulta: object
    campo_data: str
    agregados: dict
    metricas: dict
    separar_por: str | None = None
    campo_objeto: str | None = None
    aditiva: bool = True
    campo_e_data: bool = False
    #: (alvo, eventos) quando a fonte é a tabela nova de interações
    registro: tuple | None = None
    #: dobra o ranking (ex.: os brinquedos de cada evento viram o evento)
    agrupar_ranking: Callable | None = None
    #: quando o objeto do ranking é uma expressão (ex.: "tipo:id" da linha de pedido)
    expressao_objeto: object = None
    #: o ranking conta outra coisa que a série (as contas ativas contam
    #: PESSOAS por dia; o ranking delas, os DIAS de cada pessoa)
    agregados_ranking: dict | None = None
    #: Hoje, numa fonte de pessoas distintas que só guarda o dia: quem são
    #: (janela -> {"total", "itens"}), para a linha do tempo do dia
    pessoas: Callable | None = None
    #: uma lista no lugar do ranking (janela -> {"titulo", "sub", "itens"}):
    #: os cadastros mais recentes, por exemplo
    lista: Callable | None = None


@dataclass
class _Acumulado:
    metrica: Metrica
    n: int
    serie: list = field(default_factory=list)
    anterior: list = field(default_factory=list)
    semana: list = field(default_factory=lambda: [0] * 7)
    total: object = 0
    total_anterior: object = 0
    tem_linhas: bool = False
    ranking: dict = field(default_factory=dict)
    sem_serie: bool = False
    #: a consulta desta métrica falhou (o erro foi para o log): o painel mostra as outras
    indisponivel: bool = False
    #: por que não há série: "distintas" (pessoas distintas não se somam hora a hora) ou
    #: "por_dia" (o registro só guarda o dia)
    motivo_sem_serie: str = ""
    fontes: list = field(default_factory=list)
    desde: dt.datetime | None = None
    comparavel: bool = True
    distinta: bool = False
    pessoas: dict | None = None
    lista: dict | None = None

    def __post_init__(self):
        self.serie = [0] * self.n
        self.anterior = [0] * self.n


def _numero(valor):
    if valor is None:
        return 0
    if isinstance(valor, Decimal):
        return valor
    return valor


def _json_numero(valor, formato):
    if valor is None:
        return None
    if isinstance(valor, Decimal):
        return float(valor.quantize(Decimal("0.01")))
    if formato == "dinheiro":
        return round(float(valor), 2)
    if isinstance(valor, float):
        return round(valor, 2)
    return valor


def _trunc(campo, kind, campo_e_data=False):
    if campo_e_data:
        return Trunc(campo, kind, output_field=DateField())
    return Trunc(campo, kind, output_field=DateTimeField(), tzinfo=_fuso())


def _cobertura(alvo, eventos):
    """Desde quando a tabela de interações tem linhas deste alvo (cache de 10 min)."""
    from .models import InteracaoPorHora

    chave = f"lsa:cobertura:{alvo}:{','.join(sorted(eventos))}"
    guardado = cache.get(chave)
    if guardado is not None:
        return guardado or None
    primeiro = InteracaoPorHora.objects.filter(alvo=alvo, evento__in=eventos).aggregate(p=Min("hora"))["p"]
    cache.set(chave, primeiro or "", 600)
    return primeiro


def _acumular_aditiva(fonte, jan, acc, indice):
    """Uma consulta: série atual, série anterior e dia da semana."""
    # A fonte que só sabe o DIA (um DateField: os dias com acesso) não tem hora a hora. No
    # "Hoje" ela é somada por dia -- o total e a comparação com ontem ficam certos -- e a
    # métrica avisa que não tem série (truncar um DateField por hora é um erro do Django:
    # era o 500 da aba Gráficos da ficha do usuário).
    so_o_dia = fonte.campo_e_data and jan.unidade == "hora"
    kind = "hour" if (jan.unidade == "hora" and not so_o_dia) else "day"
    if so_o_dia:
        pessoas = fonte.pessoas(jan) if (fonte.pessoas and jan.dias == 1) else None
        for codigo in set(fonte.metricas.values()):
            if codigo in acc:
                acc[codigo].sem_serie = True
                acc[codigo].motivo_sem_serie = "por_dia"
                acc[codigo].anterior = None
                acc[codigo].pessoas = pessoas
    valores = [fonte.separar_por] if fonte.separar_por else []
    linhas = (
        fonte.consulta.filter(jan.filtro(fonte.campo_data, campo_e_data=fonte.campo_e_data))
        .annotate(_t=_trunc(fonte.campo_data, kind, fonte.campo_e_data))
        .values(*valores, "_t")
        .annotate(**fonte.agregados)
        .order_by()
    )
    inicio = _local_ingenuo(jan.inicio)
    for linha in linhas:
        momento = _local_ingenuo(linha["_t"])
        if momento is None:
            continue
        atual = momento >= inicio
        balde = balde_de(momento if atual else momento + jan.duracao, jan.unidade)
        posicao = None if so_o_dia else indice.get(balde)
        separador = linha.get(fonte.separar_por) if fonte.separar_por else None
        for apelido in fonte.agregados:
            codigo = fonte.metricas.get((separador, apelido))
            if codigo not in acc:
                continue
            valor = _numero(linha[apelido])
            alvo = acc[codigo]
            alvo.tem_linhas = True
            if atual:
                alvo.total += valor
                if posicao is not None:
                    alvo.serie[posicao] += valor
                if jan.unidade != "hora":
                    alvo.semana[momento.weekday()] += valor
            else:
                alvo.total_anterior += valor
                if posicao is not None and alvo.anterior is not None:
                    alvo.anterior[posicao] += valor


def _acumular_distinta(fonte, jan, acc, indice):
    """Pessoas distintas: totais por agregação condicional, série na unidade do período."""
    atual = jan.filtro(fonte.campo_data, so_atual=True, campo_e_data=fonte.campo_e_data)
    todas = jan.filtro(fonte.campo_data, campo_e_data=fonte.campo_e_data)
    anterior = todas & ~atual
    for apelido, agregado in fonte.agregados.items():
        codigo = fonte.metricas.get((None, apelido))
        if codigo not in acc:
            continue
        alvo = acc[codigo]
        campo_contado = agregado.source_expressions[0]
        totais = fonte.consulta.filter(todas).aggregate(
            atual=Count(campo_contado, distinct=True, filter=atual),
            anterior=Count(campo_contado, distinct=True, filter=anterior),
        )
        alvo.total += totais["atual"] or 0
        alvo.total_anterior += totais["anterior"] or 0
        alvo.tem_linhas = alvo.tem_linhas or bool(totais["atual"] or totais["anterior"])
        alvo.anterior = None  # a série anterior de distintos não é somável: só o total compara
        alvo.distinta = True
        alvo.semana = None
        kind = {"hora": "hour", "dia": "day", "semana": "week", "mes": "month"}.get(jan.unidade)
        if kind is None or (jan.unidade == "hora" and fonte.campo_e_data):
            # A fonte só guarda o DIA (os acessos): hora a hora não há o que
            # contar. Em vez de um gráfico vazio, vão as pessoas do dia.
            alvo.sem_serie = True
            alvo.motivo_sem_serie = alvo.motivo_sem_serie or "distintas"
            if fonte.pessoas and jan.dias == 1 and (totais["atual"] or 0):
                alvo.pessoas = fonte.pessoas(jan)
            continue
        linhas = (
            fonte.consulta.filter(atual)
            .annotate(_t=_trunc(fonte.campo_data, kind, fonte.campo_e_data))
            .values("_t")
            .annotate(v=agregado)
            .order_by()
        )
        for linha in linhas:
            posicao = indice.get(balde_de(_local_ingenuo(linha["_t"]), jan.unidade))
            if posicao is not None:
                alvo.serie[posicao] += linha["v"] or 0


def _acumular_ranking(fonte, jan, acc):
    if not fonte.campo_objeto:
        return
    if fonte.agregados_ranking and jan.dias <= 1:
        # "dias com acesso" num dia só daria 1 para todo mundo: sem ranking
        # (em Hoje a tela já mostra as pessoas do dia, uma a uma)
        return
    campos = [fonte.campo_objeto] + ([fonte.separar_por] if fonte.separar_por else [])
    consulta = fonte.consulta.filter(jan.filtro(fonte.campo_data, so_atual=True, campo_e_data=fonte.campo_e_data))
    if fonte.expressao_objeto is not None:
        consulta = consulta.annotate(**{fonte.campo_objeto: fonte.expressao_objeto})
    agregados = fonte.agregados_ranking or fonte.agregados
    linhas = (
        consulta
        .values(*campos)
        .annotate(**agregados)
        .order_by()
    )
    for linha in linhas:
        objeto = linha[fonte.campo_objeto]
        if objeto in (None, ""):
            continue
        separador = linha.get(fonte.separar_por) if fonte.separar_por else None
        destinos = fonte.agrupar_ranking(objeto) if fonte.agrupar_ranking else [objeto]
        for apelido in agregados:
            codigo = fonte.metricas.get((separador, apelido))
            if codigo not in acc:
                continue
            valor = _numero(linha[apelido])
            if not valor:
                continue
            for destino in destinos:
                acc[codigo].ranking[destino] = acc[codigo].ranking.get(destino, 0) + valor


def _variacao(atual, anterior):
    if not anterior:
        return (None, "igual") if not atual else (None, "novo")
    variacao = float((Decimal(str(atual)) - Decimal(str(anterior))) / Decimal(str(anterior)) * 100)
    if abs(variacao) < 0.05:
        return 0.0, "igual"
    return round(variacao, 1), ("sobe" if variacao > 0 else "desce")


def _dividir(a, b):
    if not b:
        return None
    return float(Decimal(str(a)) / Decimal(str(b)))


# ======================================================================
# A CONTA
# ======================================================================

def calcular(tipo, jan, objeto_id=None, usar_cache=True):
    """O dicionário que vira o JSON do painel."""
    chave = None
    if usar_cache:
        chave = (
            f"lsa:v2:{tipo.codigo}:{objeto_id or '-'}:{jan.codigo}:"
            f"{jan.de or ''}:{jan.ate or ''}:{timezone.localtime(jan.inicio):%Y%m%d}"
        )
        guardado = cache.get(chave)
        if guardado is not None:
            return guardado

    baldes = jan.baldes()
    indice = {balde: posicao for posicao, balde in enumerate(baldes)}
    agora_local = _local_ingenuo(jan.agora)

    metricas = [
        m for m in tipo.metricas
        if not (m.so_geral and objeto_id) and not (m.so_objeto and not objeto_id)
    ]
    acc = {m.codigo: _Acumulado(m, len(baldes)) for m in metricas if not m.razao}

    fontes = tipo.fontes(objeto_id)
    houve_falha = False
    for fonte in fontes:
        for (separador, _apelido), codigo in fonte.metricas.items():
            if codigo in acc and (fonte, separador) not in acc[codigo].fontes:
                acc[codigo].fontes.append((fonte, separador))
        # UMA FONTE COM DEFEITO NÃO DERRUBA O PAINEL. O cliente, com o "O servidor
        # respondeu 500" na ficha do usuário: "você não pode me gerar uma coisa gerando
        # erros". Cada fonte roda num ponto de retorno: se a consulta dela falhar, o erro vai
        # para o log (com o tipo, o objeto e o período), as métricas dela saem como
        # "indisponível" e as outras continuam certas -- e a resposta não fica em cache.
        try:
            with _ponto_de_retorno():
                if fonte.aditiva:
                    _acumular_aditiva(fonte, jan, acc, indice)
                else:
                    _acumular_distinta(fonte, jan, acc, indice)
                if objeto_id is None:
                    _acumular_ranking(fonte, jan, acc)
                    if fonte.lista:
                        for (_separador, _apelido), codigo in fonte.metricas.items():
                            if codigo in acc and acc[codigo].lista is None:
                                acc[codigo].lista = fonte.lista(jan)
        except Exception:  # noqa: BLE001 -- o painel segue com o que deu certo
            log.exception(
                "analises: a fonte %s falhou (tipo=%s objeto=%s periodo=%s)",
                fonte.chave, tipo.codigo, objeto_id, jan.codigo,
            )
            houve_falha = True
            for codigo in set(fonte.metricas.values()):
                if codigo in acc:
                    acc[codigo].indisponivel = True

    # cobertura da tabela nova de interações e "sem dados" das demais
    existe = {}

    def tem_alguma_linha(fonte, separador):
        """Fora das duas janelas, este objeto/tipo já teve alguma linha? (uma vez por fonte)"""
        chave_existe = (id(fonte), separador)
        if chave_existe not in existe:
            consulta = fonte.consulta
            if separador is not None and fonte.separar_por:
                consulta = consulta.filter(**{fonte.separar_por: separador})
            try:
                with _ponto_de_retorno():
                    existe[chave_existe] = consulta.exists()
            except Exception:  # noqa: BLE001 -- a fonte com defeito já foi para o log
                existe[chave_existe] = False
        return existe[chave_existe]

    for codigo, alvo in acc.items():
        registradas = [fonte for fonte, _ in alvo.fontes if fonte.registro]
        for fonte in registradas:
            # O registro por hora vale para todo o catálogo desde o primeiro
            # dia: sem linha nenhuma é "sem dados ainda"; com linhas, zero é zero.
            desde = _cobertura(*fonte.registro)
            alvo.desde = desde
            if desde is None:
                alvo.tem_linhas = False
            else:
                alvo.tem_linhas = True
                if desde > jan.anterior_inicio:
                    alvo.comparavel = False
        if not registradas and not alvo.tem_linhas:
            alvo.tem_linhas = any(tem_alguma_linha(fonte, separador) for fonte, separador in alvo.fontes)

    # nomes do ranking, numa consulta por tipo
    ids = set()
    for alvo in acc.values():
        ids.update(alvo.ranking)
    nomes = tipo.nomes(ids) if (ids and tipo.nomes) else {}

    tons = {m.codigo: TONS[posicao % len(TONS)] for posicao, m in enumerate(tipo.metricas)}
    resultado_metricas = []
    for metrica in metricas:
        serializada = _serializar(metrica, acc, baldes, agora_local, jan, nomes)
        serializada["tom"] = tons.get(metrica.codigo, TONS[0])
        resultado_metricas.append(serializada)
    # a métrica que o gráfico abre: a principal do tipo, se tiver dado; senão a primeira que tem
    com_dados = [m["codigo"] for m in resultado_metricas if not m["vazia"]]
    principal = tipo.principal if tipo.principal in com_dados else (com_dados[0] if com_dados else tipo.principal)
    textos = jan.textos()

    rotulos = []
    inicio_janela = _local_ingenuo(jan.inicio)
    for balde in baldes:
        curto, longo = rotulo_do_balde(balde, jan.unidade, inicio_janela)
        rotulos.append({
            "chave": balde.isoformat(),
            "curto": curto,
            "longo": longo,
            "futuro": balde > agora_local,
        })

    resposta = {
        "tipo": tipo.codigo,
        "tipo_rotulo": tipo.rotulo,
        "objeto": None,
        "periodo": {
            "codigo": jan.codigo,
            "rotulo": jan.rotulo,
            "unidade": jan.unidade,
            "inicio": timezone.localtime(jan.inicio).isoformat(),
            "fim": timezone.localtime(jan.fim).isoformat(),
            "anterior_inicio": timezone.localtime(jan.anterior_inicio).isoformat(),
            "anterior_fim": timezone.localtime(jan.anterior_fim).isoformat(),
            "descricao": jan.descricao(),
            "titulo": textos["titulo"],
            "comparacao": textos["comparacao"],
            "anterior_curto": textos["anterior_curto"],
            "dias": jan.dias,
            "de": jan.de.isoformat() if jan.de else None,
            "ate": jan.ate.isoformat() if jan.ate else None,
        },
        "rotulos": rotulos,
        "dias_da_semana": list(DIAS_DA_SEMANA_LONGOS),
        "metricas": resultado_metricas,
        "principal": principal,
        "ranking_titulo": tipo.ranking_titulo,
        "avisos": list(tipo.avisos),
        "gerado_em": timezone.localtime(jan.agora).isoformat(),
    }
    if chave and not houve_falha:
        cache.set(chave, resposta, CACHE_SEGUNDOS)
    return resposta


def _motivo(sem_dados, desde, indisponivel=False):
    """Por que a métrica não tem número neste período, dito sem jargão."""
    if indisponivel:
        return "Não deu para carregar agora; o erro foi registrado. Os outros números estão certos."
    if sem_dados:
        return "Nenhum registro até hoje."
    if desde:
        return f"Registrado desde {timezone.localtime(desde):%d/%m/%Y}: nada neste período."
    return "Sem movimento neste período nem no anterior."


def _serializar(metrica, acc, baldes, agora_local, jan, nomes):
    futuros = [balde > agora_local for balde in baldes]

    if metrica.razao:
        numerador, denominador = (acc.get(c) for c in metrica.razao)
        if numerador is None or denominador is None:
            return {"codigo": metrica.codigo, "rotulo": metrica.rotulo, "sem_dados": True}
        total = _dividir(numerador.total, denominador.total)
        anterior = _dividir(numerador.total_anterior, denominador.total_anterior)
        serie = [None if futuros[i] else _dividir(numerador.serie[i], denominador.serie[i]) for i in range(len(baldes))]
        serie_anterior = None
        if numerador.anterior is not None and denominador.anterior is not None:
            serie_anterior = [_dividir(numerador.anterior[i], denominador.anterior[i]) for i in range(len(baldes))]
        variacao, direcao = _variacao(total or 0, anterior or 0)
        indisponivel = numerador.indisponivel or denominador.indisponivel
        sem_dados = not (numerador.tem_linhas and denominador.tem_linhas) or indisponivel
        vazia = sem_dados or not (total or anterior)
        return {
            "codigo": metrica.codigo,
            "rotulo": metrica.rotulo,
            "icone": metrica.icone,
            "formato": metrica.formato,
            "ajuda": metrica.ajuda,
            "subir_e_bom": metrica.subir_e_bom,
            "sem_dados": sem_dados,
            "indisponivel": indisponivel,
            "vazia": vazia,
            "motivo": _motivo(sem_dados, None, indisponivel) if vazia else "",
            "forma": "linha",
            "titulos": None,
            "distinta": False,
            "pessoas": None,
            "lista": None,
            "ranking_unidade": None,
            "comparavel": numerador.comparavel and denominador.comparavel,
            "desde": None,
            "total": _json_numero(total, metrica.formato),
            "anterior": _json_numero(anterior, metrica.formato),
            "variacao": variacao,
            "direcao": direcao,
            "serie": [_json_numero(v, metrica.formato) for v in serie],
            "serie_anterior": [_json_numero(v, metrica.formato) for v in serie_anterior] if serie_anterior else None,
            "semana": None,
            "ranking": [],
            "tem_ranking": False,
            "razao": True,
        }

    alvo = acc[metrica.codigo]
    variacao, direcao = _variacao(alvo.total, alvo.total_anterior)
    ranking = []
    for objeto, valor in sorted(alvo.ranking.items(), key=lambda par: (-float(par[1]), str(par[0])))[:RANKING_TAMANHO]:
        nome = nomes.get(objeto, {}) if isinstance(nomes.get(objeto), dict) else {"nome": nomes.get(objeto)}
        item = {
            "id": nome.get("id", objeto),
            "nome": nome.get("nome") or f"#{objeto}",
            "tipo": nome.get("tipo"),
            "valor": _json_numero(valor, metrica.formato),
        }
        # o ranking de pessoas (Usuários) leva o avatar e a última vez em que a conta foi vista
        for extra in ("avatar", "detalhe", "online"):
            if nome.get(extra) is not None:
                item[extra] = nome[extra]
        ranking.append(item)
    sem_dados = not alvo.tem_linhas or alvo.indisponivel
    vazia = sem_dados or not (alvo.total or alvo.total_anterior)
    return {
        "codigo": metrica.codigo,
        "rotulo": metrica.rotulo,
        "icone": metrica.icone,
        "formato": metrica.formato,
        "ajuda": metrica.ajuda,
        "subir_e_bom": metrica.subir_e_bom,
        "sem_dados": sem_dados,
        "indisponivel": alvo.indisponivel,
        "vazia": vazia,
        "motivo": _motivo(sem_dados, alvo.desde, alvo.indisponivel) if vazia else "",
        # pessoas distintas não se somam de um balde para o outro: colunas, e não uma linha contínua
        "forma": metrica.forma or ("colunas" if alvo.distinta else "linha"),
        "titulos": metrica.titulos,
        "distinta": alvo.distinta,
        "pessoas": alvo.pessoas,
        "lista": alvo.lista,
        "ranking_unidade": list(metrica.ranking_unidade) if metrica.ranking_unidade else None,
        "comparavel": alvo.comparavel,
        "desde": timezone.localtime(alvo.desde).date().isoformat() if alvo.desde else None,
        "total": _json_numero(alvo.total, metrica.formato),
        "anterior": _json_numero(alvo.total_anterior, metrica.formato),
        "variacao": variacao if alvo.comparavel else None,
        "direcao": direcao if alvo.comparavel else "sem_base",
        "serie": None if alvo.sem_serie else [
            None if futuros[i] else _json_numero(v, metrica.formato) for i, v in enumerate(alvo.serie)
        ],
        "motivo_sem_serie": (alvo.motivo_sem_serie or "distintas") if alvo.sem_serie else None,
        "serie_anterior": None if alvo.anterior is None else [
            _json_numero(v, metrica.formato) for v in alvo.anterior
        ],
        "semana": None if (alvo.semana is None or jan.unidade == "hora") else [
            _json_numero(v, metrica.formato) for v in alvo.semana
        ],
        "ranking": ranking,
        "tem_ranking": bool(ranking) or any(
            fonte.campo_objeto and not fonte.agregados_ranking for fonte, _ in alvo.fontes
        ),
    }


def dinheiro_da_linha(preco="valor_unitario", quantidade="quantidade"):
    return Sum(F(preco) * F(quantidade), output_field=DINHEIRO)


def maior_nome(campo):
    return Max(campo)
