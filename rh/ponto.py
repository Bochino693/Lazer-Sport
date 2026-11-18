"""O ponto: bater, conferir a cadeia e montar o espelho do mês.

CONTROLE INTERNO. Isto é o registro de frequência da empresa, feito pelo
painel. Ele NÃO é um REP certificado (Portaria MTP 671/2021): se a lei
exigir REP para o porte da empresa, este controle não o substitui. Ver
LEIA-ME-V10, seção "Recursos Humanos".

AS REGRAS QUE TORNAM O REGISTRO CONFIÁVEL:

  * A HORA É DO SERVIDOR. O aparelho manda só "quero bater o ponto" (e, se
    a pessoa deixar, a localização). Relógio de celular adiantado não muda
    nada.
  * A ORDEM É CONFERIDA: entrada -> saída para intervalo -> volta -> saída.
    Não há duas entradas seguidas no mesmo dia, nem saída sem entrada.
    Dois toques em menos de um minuto viram um só (o segundo é recusado).
  * CADA MARCAÇÃO É ENCADEADA: o hash dela inclui o da anterior do mesmo
    colaborador, e o NSR (1, 2, 3...) não pula. Mudar uma linha no banco
    quebra a cadeia, e `conferir_cadeia` aponta onde.
  * NADA SE EDITA NEM SE APAGA (models.MarcacaoPonto e o gatilho da
    migração 0002). Correção é um AJUSTE, à parte, com justificativa,
    decidido pela Gestão. O espelho mostra os dois.
  * O dia vai da meia-noite à meia-noite (horário de Brasília). Jornada
    que atravessa a meia-noite não é tratada por este controle.
"""

from __future__ import annotations

import calendar
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from .models import AjustePonto, Colaborador, MarcacaoPonto, Situacao, TipoMarcacao

#: Depois de uma marcação, o que pode vir a seguir no mesmo dia.
PROXIMAS = {
    None: (TipoMarcacao.ENTRADA,),
    TipoMarcacao.ENTRADA: (TipoMarcacao.SAIDA_INTERVALO, TipoMarcacao.SAIDA),
    TipoMarcacao.SAIDA_INTERVALO: (TipoMarcacao.VOLTA_INTERVALO,),
    TipoMarcacao.VOLTA_INTERVALO: (TipoMarcacao.SAIDA, TipoMarcacao.SAIDA_INTERVALO),
    TipoMarcacao.SAIDA: (TipoMarcacao.ENTRADA,),
}
ABRE = (TipoMarcacao.ENTRADA, TipoMarcacao.VOLTA_INTERVALO)
FECHA = (TipoMarcacao.SAIDA_INTERVALO, TipoMarcacao.SAIDA)

#: Um toque repetido não vira duas marcações.
INTERVALO_MINIMO = timedelta(seconds=60)
#: CLT, art. 58, § 1º: variações de até 5 minutos por marcação, no máximo
#: 10 por dia, não contam como atraso nem como extra.
TOLERANCIA_ATRASO = 5
TOLERANCIA_DIA = 10
#: Para "quem falta hoje": depois de quanto tempo da entrada da jornada.
FOLGA_PARA_FALTA = 15


class ErroDePonto(Exception):
    pass


# ======================================================================
# FERIADOS NACIONAIS
# ======================================================================
def _pascoa(ano: int) -> date:
    """Domingo de Páscoa (algoritmo de Meeus/Jones/Butcher)."""
    a = ano % 19
    b, c = divmod(ano, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    mes = (h + l_ - 7 * m + 114) // 31
    dia = ((h + l_ - 7 * m + 114) % 31) + 1
    return date(ano, mes, dia)


def feriados_nacionais(ano: int) -> dict[date, str]:
    """Os feriados nacionais (Leis 662/1949, 6.802/1980, 9.093/1995 e 14.759/2023).

    Estaduais e municipais (o aniversário da cidade, o 9 de julho em SP, o
    Corpus Christi onde é feriado) entram como ABONO, pelo ajuste de ponto.
    """
    return {
        date(ano, 1, 1): "Confraternização Universal",
        _pascoa(ano) - timedelta(days=2): "Sexta-feira Santa",
        date(ano, 4, 21): "Tiradentes",
        date(ano, 5, 1): "Dia do Trabalho",
        date(ano, 9, 7): "Independência",
        date(ano, 10, 12): "Nossa Senhora Aparecida",
        date(ano, 11, 2): "Finados",
        date(ano, 11, 15): "Proclamação da República",
        date(ano, 11, 20): "Dia da Consciência Negra",
        date(ano, 12, 25): "Natal",
    }


# ======================================================================
# BATER O PONTO
# ======================================================================
def marcacoes_do_dia(colaborador, dia: date):
    return list(MarcacaoPonto.objects.filter(colaborador=colaborador, data=dia).order_by("momento", "id"))


def proximas_do_dia(marcacoes) -> tuple:
    ultima = marcacoes[-1].tipo if marcacoes else None
    return PROXIMAS[ultima]


def _coordenada(valor, limite):
    if valor in (None, ""):
        return None
    try:
        numero = Decimal(str(valor).replace(",", ".")).quantize(Decimal("0.000001"))
    except (InvalidOperation, ValueError):
        return None
    if numero.is_nan() or abs(numero) > limite:
        return None
    return numero


def registrar(colaborador, tipo=None, *, ip=None, navegador="", latitude=None, longitude=None, precisao=None):
    """Grava a próxima marcação do colaborador, com a hora do servidor."""
    lat = _coordenada(latitude, 90)
    lng = _coordenada(longitude, 180)
    if lat is None or lng is None:
        lat = lng = None
        precisao_m = None
    else:
        try:
            precisao_m = max(0, min(100_000, int(float(precisao)))) if precisao not in (None, "") else None
        except (TypeError, ValueError, OverflowError):
            precisao_m = None

    with transaction.atomic():
        # A linha do colaborador travada: dois aparelhos batendo juntos
        # entram em fila, e a cadeia (NSR e hash) não se bifurca.
        colaborador = Colaborador.objects.select_for_update().get(pk=colaborador.pk)
        if colaborador.situacao != Situacao.ATIVO:
            raise ErroDePonto(
                f"O cadastro está como “{colaborador.get_situacao_display()}”: "
                "o ponto só vale para quem está ativo. Fale com a Gestão."
            )
        agora = timezone.now()
        hoje = timezone.localdate(agora)
        if colaborador.data_admissao and hoje < colaborador.data_admissao:
            raise ErroDePonto("A admissão ainda não chegou: o ponto começa no dia da admissão.")

        do_dia = marcacoes_do_dia(colaborador, hoje)
        permitidas = proximas_do_dia(do_dia)
        if not tipo:
            tipo = permitidas[0]
        if tipo not in TipoMarcacao.values:
            raise ErroDePonto("Tipo de marcação inválido.")
        if tipo not in permitidas:
            agora_texto = ", ".join(TipoMarcacao(t).label.lower() for t in permitidas)
            raise ErroDePonto(
                f"Agora não cabe “{TipoMarcacao(tipo).label.lower()}”. O próximo registro é: "
                f"{agora_texto}. Se esqueceu alguma marcação, peça um ajuste."
            )
        if do_dia and agora - do_dia[-1].momento < INTERVALO_MINIMO:
            ultima = do_dia[-1]
            raise ErroDePonto(
                f"Você acabou de registrar “{ultima.get_tipo_display().lower()}” às "
                f"{ultima.hora_local:%H:%M}. Espere um minuto para a próxima."
            )

        anterior = (
            MarcacaoPonto.objects.filter(colaborador=colaborador).order_by("-nsr").only("nsr", "hash").first()
        )
        marcacao = MarcacaoPonto(
            colaborador=colaborador,
            nsr=(anterior.nsr + 1) if anterior else 1,
            tipo=tipo,
            momento=agora,
            data=hoje,
            ip=ip or None,
            navegador=(navegador or "")[:300],
            latitude=lat,
            longitude=lng,
            precisao_m=precisao_m,
            hash_anterior=anterior.hash if anterior else "",
        )
        marcacao.hash = marcacao.calcular_hash()
        marcacao.save()
    return marcacao


def conferir_cadeia(colaborador) -> list[str]:
    """Refaz a conta de cada marcação. Lista vazia: a cadeia está íntegra."""
    problemas = []
    anterior = None
    for marcacao in MarcacaoPonto.objects.filter(colaborador=colaborador).order_by("nsr"):
        esperado_nsr = (anterior.nsr + 1) if anterior else 1
        if marcacao.nsr != esperado_nsr:
            problemas.append(f"NSR {marcacao.nsr}: esperado {esperado_nsr} (falta registro na sequência).")
        if marcacao.hash_anterior != (anterior.hash if anterior else ""):
            problemas.append(f"NSR {marcacao.nsr}: não está preso à marcação anterior.")
        if marcacao.hash != marcacao.calcular_hash():
            problemas.append(f"NSR {marcacao.nsr}: o conteúdo não confere com o hash gravado.")
        anterior = marcacao
    return problemas


# ======================================================================
# O ESPELHO DO MÊS
# ======================================================================
def hm(minutos: int) -> str:
    """480 -> "8h00"; negativo com sinal."""
    sinal = "-" if minutos < 0 else ""
    minutos = abs(int(minutos))
    return f"{sinal}{minutos // 60}h{minutos % 60:02d}"


def _min(hora) -> int:
    return hora.hour * 60 + hora.minute


@dataclass
class Evento:
    hora: time
    tipo: str
    origem: str  # "registro" ou "ajuste"
    marcacao: MarcacaoPonto | None = None
    ajuste: AjustePonto | None = None
    desconsiderada: bool = False
    pendente: bool = False

    @property
    def rotulo(self):
        return TipoMarcacao(self.tipo).label


@dataclass
class Dia:
    data: date
    eventos: list = field(default_factory=list)
    esperado: int = 0
    trabalhado: int = 0
    intervalo: int = 0
    atraso: int = 0
    extra: int = 0
    extra_100: int = 0
    debito: int = 0
    falta: bool = False
    incompleto: bool = False
    em_andamento: bool = False
    intervalo_curto: bool = False
    feriado: str = ""
    abono: AjustePonto | None = None
    futuro: bool = False
    fora_do_contrato: bool = False
    pendentes: int = 0

    @property
    def semana(self):
        return ("Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom")[self.data.weekday()]

    @property
    def dia_util(self):
        return self.esperado > 0

    @property
    def saldo(self):
        return self.extra + self.extra_100 - self.debito

    @property
    def efetivos(self):
        return [e for e in self.eventos if not e.desconsiderada and not e.pendente]


@dataclass
class Espelho:
    colaborador: Colaborador
    ano: int
    mes: int
    dias: list
    integridade: list

    def _soma(self, campo):
        return sum(getattr(d, campo) for d in self.dias)

    @property
    def inicio(self):
        return date(self.ano, self.mes, 1)

    @property
    def totais(self):
        trabalhado = self._soma("trabalhado")
        extra = self._soma("extra")
        extra_100 = self._soma("extra_100")
        debito = self._soma("debito")
        return {
            "esperado": hm(self._soma("esperado")),
            "trabalhado": hm(trabalhado),
            "extra": hm(extra),
            "extra_100": hm(extra_100),
            "debito": hm(debito),
            "saldo": hm(extra + extra_100 - debito),
            "saldo_minutos": extra + extra_100 - debito,
            "atrasos": sum(1 for d in self.dias if d.atraso),
            "atraso_min": hm(self._soma("atraso")),
            "faltas": sum(1 for d in self.dias if d.falta),
            "dias_trabalhados": sum(1 for d in self.dias if d.trabalhado),
            "incompletos": sum(1 for d in self.dias if d.incompleto),
            "abonos": sum(1 for d in self.dias if d.abono),
            "intervalos_curtos": sum(1 for d in self.dias if d.intervalo_curto),
            "pendentes": self._soma("pendentes"),
        }

    @property
    def integro(self):
        return not self.integridade


def espelho(colaborador: Colaborador, ano: int, mes: int, *, agora=None, com_integridade=True) -> Espelho:
    agora = timezone.localtime(agora or timezone.now())
    hoje = agora.date()
    primeiro = date(ano, mes, 1)
    ultimo = date(ano, mes, calendar.monthrange(ano, mes)[1])
    feriados = feriados_nacionais(ano)

    marcacoes = list(
        MarcacaoPonto.objects.filter(colaborador=colaborador, data__range=(primeiro, ultimo)).order_by("momento", "id")
    )
    ajustes = list(
        AjustePonto.objects.filter(colaborador=colaborador, data__range=(primeiro, ultimo))
        .exclude(situacao=AjustePonto.Estado.RECUSADO)
        .select_related("marcacao")
    )
    desconsideradas = {
        a.marcacao_id: a for a in ajustes
        if a.tipo == AjustePonto.Tipo.DESCONSIDERAR
    }
    por_dia = defaultdict(list)
    for m in marcacoes:
        ajuste = desconsideradas.get(m.pk)
        aprovado = bool(ajuste and ajuste.situacao == AjustePonto.Estado.APROVADO)
        por_dia[m.data].append(Evento(
            hora=m.hora_local.time().replace(second=0, microsecond=0), tipo=m.tipo, origem="registro",
            marcacao=m, ajuste=ajuste, desconsiderada=aprovado,
        ))
    abonos = {}
    pendentes_por_dia = defaultdict(int)
    for a in ajustes:
        pendente = a.situacao == AjustePonto.Estado.PENDENTE
        if pendente:
            pendentes_por_dia[a.data] += 1
        if a.tipo == AjustePonto.Tipo.INCLUIR and a.hora:
            por_dia[a.data].append(Evento(
                hora=a.hora.replace(second=0, microsecond=0), tipo=a.tipo_marcacao,
                origem="ajuste", ajuste=a, pendente=pendente,
            ))
        elif a.tipo == AjustePonto.Tipo.ABONO and not pendente:
            abonos[a.data] = a

    dias = []
    for numero in range(1, ultimo.day + 1):
        d = date(ano, mes, numero)
        dia = Dia(data=d, feriado=feriados.get(d, ""), abono=abonos.get(d), futuro=d > hoje,
                  pendentes=pendentes_por_dia.get(d, 0))
        dia.eventos = sorted(por_dia.get(d, []), key=lambda e: (e.hora, 0 if e.origem == "registro" else 1))
        dia.fora_do_contrato = not colaborador.empregado_em(d)
        previsto = (
            not dia.fora_do_contrato and colaborador.trabalha_no_dia(d) and not dia.feriado and not dia.abono
        )
        dia.esperado = colaborador.jornada_minutos if previsto else 0
        _calcular_dia(dia, colaborador, hoje, agora)
        dias.append(dia)

    integridade = conferir_cadeia(colaborador) if com_integridade else []
    return Espelho(colaborador=colaborador, ano=ano, mes=mes, dias=dias, integridade=integridade)


def _calcular_dia(dia: Dia, colaborador: Colaborador, hoje: date, agora: datetime):
    if dia.futuro:
        dia.esperado = 0  # o que ainda não aconteceu não entra na conta
        return
    aberto = None
    intervalo_desde = None
    for evento in dia.efetivos:
        minuto = _min(evento.hora)
        if evento.tipo in ABRE:
            if aberto is not None:
                dia.incompleto = True
            if evento.tipo == TipoMarcacao.VOLTA_INTERVALO and intervalo_desde is not None:
                dia.intervalo += max(0, minuto - intervalo_desde)
                intervalo_desde = None
            aberto = minuto
        else:
            if aberto is None:
                dia.incompleto = True
                continue
            dia.trabalhado += max(0, minuto - aberto)
            aberto = None
            if evento.tipo == TipoMarcacao.SAIDA_INTERVALO:
                intervalo_desde = minuto
    if aberto is not None or intervalo_desde is not None:
        if dia.data == hoje:
            dia.em_andamento = True
            if aberto is not None:
                dia.trabalhado += max(0, _min(agora.time()) - aberto)
        else:
            dia.incompleto = True

    efetivos = dia.efetivos
    if dia.dia_util and efetivos:
        primeira = next((e for e in efetivos if e.tipo == TipoMarcacao.ENTRADA), None)
        if primeira:
            atraso = _min(primeira.hora) - _min(colaborador.jornada_inicio)
            if atraso > TOLERANCIA_ATRASO:
                dia.atraso = atraso

    if dia.dia_util and not efetivos:
        terminou = dia.data < hoje or _min(agora.time()) > _min(colaborador.jornada_fim)
        if terminou:
            dia.falta = True
            dia.debito = dia.esperado
        return

    if dia.em_andamento:
        return  # o dia de hoje ainda não fechou: sem saldo

    if dia.trabalhado > 6 * 60 and dia.intervalo < 60 and not dia.incompleto:
        dia.intervalo_curto = True

    saldo = dia.trabalhado - dia.esperado
    if abs(saldo) <= TOLERANCIA_DIA:
        saldo = 0
    if saldo > 0:
        domingo_ou_feriado = dia.data.isoweekday() == 7 or bool(dia.feriado)
        if not dia.dia_util and domingo_ou_feriado:
            dia.extra_100 = saldo
        else:
            dia.extra = saldo
    elif saldo < 0:
        dia.debito = -saldo


def mes_do_texto(texto: str, padrao: date | None = None) -> tuple[int, int]:
    padrao = padrao or timezone.localdate()
    achado = re.fullmatch(r"(\d{4})-(\d{1,2})", (texto or "").strip())
    if achado:
        ano, mes = int(achado.group(1)), int(achado.group(2))
        if 2000 <= ano <= 2100 and 1 <= mes <= 12:
            return ano, mes
    return padrao.year, padrao.month


def mes_anterior(ano, mes):
    return (ano - 1, 12) if mes == 1 else (ano, mes - 1)


def mes_seguinte(ano, mes):
    return (ano + 1, 1) if mes == 12 else (ano, mes + 1)


MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro")


def nome_do_mes(ano, mes):
    return f"{MESES[mes - 1]} de {ano}"


# ======================================================================
# QUEM ESTÁ TRABALHANDO, QUEM FALTA (o painel do RH)
# ======================================================================
def situacao_de_hoje(agora=None):
    """Para o painel: quem está trabalhando, em intervalo, falta ou ainda não começou."""
    agora = timezone.localtime(agora or timezone.now())
    hoje = agora.date()
    feriado = feriados_nacionais(hoje.year).get(hoje, "")
    ativos = list(Colaborador.objects.filter(situacao=Situacao.ATIVO).order_by("nome"))
    ultima = {}
    for m in MarcacaoPonto.objects.filter(data=hoje).order_by("momento", "id"):
        ultima[m.colaborador_id] = m
    abonados = set(
        AjustePonto.objects.filter(
            data=hoje, tipo=AjustePonto.Tipo.ABONO, situacao=AjustePonto.Estado.APROVADO,
        ).values_list("colaborador_id", flat=True)
    )
    trabalhando, intervalo, faltando, aguardando, encerrados = [], [], [], [], []
    for c in ativos:
        m = ultima.get(c.pk)
        if m is not None:
            if m.tipo in ABRE:
                trabalhando.append((c, m))
            elif m.tipo == TipoMarcacao.SAIDA_INTERVALO:
                intervalo.append((c, m))
            else:
                encerrados.append((c, m))
            continue
        if feriado or c.pk in abonados or not c.trabalha_no_dia(hoje) or not c.empregado_em(hoje):
            continue
        limite = _min(c.jornada_inicio) + FOLGA_PARA_FALTA
        if _min(agora.time()) >= limite:
            faltando.append(c)
        else:
            aguardando.append(c)
    return {
        "trabalhando": trabalhando,
        "intervalo": intervalo,
        "faltando": faltando,
        "aguardando": aguardando,
        "encerrados": encerrados,
        "feriado": feriado,
    }
