"""Recursos humanos: colaboradores, documentos, ponto e tarefas.

Cinco peças, e as regras que não podem ser quebradas moram AQUI, no modelo
(e não só no formulário), porque qualquer caminho de gravação -- tela,
admin, script, a produção chamando `rh.tarefas.atribuir` -- passa por elas:

  * COLABORADOR: a ficha completa. CPF e PIS conferidos pelos dígitos e
    únicos; datas coerentes (admissão até hoje, desligamento depois da
    admissão, idade mínima pelo vínculo). O SETOR casa com as funções do
    painel (`sistema_interno.permissoes.FUNCOES`): é por ele que a produção
    sugere quem faz cada etapa.
  * DOCUMENTO: o arquivo nunca tem endereço público (ver armazenamento.py).
  * MARCAÇÃO DE PONTO: hora do servidor, encadeada por hash, e IMUTÁVEL --
    não se edita nem se apaga, nem pelo admin, nem por `QuerySet.update`,
    nem pelo banco (gatilho na migração 0002).
  * AJUSTE DE PONTO: a correção é um registro separado, com justificativa,
    pedido pelo colaborador e decidido pela Gestão. Os dois ficam à vista.
  * TAREFA: avulsa ou ligada a qualquer coisa do sistema (uma etapa da
    produção, um pedido, uma O.S.) por chave genérica. Ver tarefas.py.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date, time, timedelta
from datetime import timezone as dt_timezone
from decimal import Decimal

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import models
from django.db.models import Q
from django.utils import timezone

from sistema_interno.validacoes import cnpj_valido, cpf_valido, somente_digitos, telefone_valido

from .armazenamento import armazenamento_privado
from .validadores import (
    IDADE_MAXIMA,
    IDADE_MINIMA,
    formatar_cep,
    formatar_cpf,
    formatar_pis,
    formatar_telefone,
    idade_em,
    mascarar_cpf,
    validar_cep,
    validar_cpf,
    validar_pis,
    validar_telefone,
    validar_uf,
)


class RegistroImutavel(Exception):
    """Marcação de ponto (e registro de auditoria) não se edita nem se apaga."""


# ======================================================================
# ESCOLHAS
# ======================================================================
class Setor(models.TextChoices):
    """O setor é a FUNÇÃO do painel (sistema_interno.permissoes.FUNCOES).

    Mesmos códigos -- há teste que confere --, para a ficha, a conta de
    acesso e a sugestão de responsável falarem a mesma língua. A Engenharia
    de produção inclui o estoque e a matéria-prima; o que cada pessoa faz
    DENTRO dela são as especialidades, abaixo.
    """

    PRODUCAO = "producao", "Engenharia de produção"
    CRIACAO = "criacao", "Criação e site"
    VENDAS = "vendas", "Vendas"
    AMBULANTE = "ambulante", "Vendedor ambulante"
    FINANCEIRO = "financeiro", "Financeiro"
    GESTAO = "gestao", "Gestão"


class Especialidade(models.TextChoices):
    """O que a pessoa faz dentro da Engenharia de produção.

    As sete etapas por que passa cada brinquedo, mais o estoque e a
    matéria-prima. É por aqui que a etapa "Adesivo" sugere quem é do
    adesivo antes do resto da produção.
    """

    ESTOQUE = "estoque", "Estoque e matéria-prima"
    CORTE = "corte", "Corte de MDF"
    MONTAGEM = "montagem", "Montagem"
    ADESIVO = "adesivo", "Adesivo"
    ELETRONICA = "eletronica", "Eletrônica"
    FINALIZACAO = "finalizacao", "Finalização"
    TESTE = "teste", "Teste de qualidade"
    EMBALAGEM = "embalagem", "Embalagem"


class Vinculo(models.TextChoices):
    CLT = "clt", "CLT"
    PJ = "pj", "PJ (prestador)"
    TEMPORARIO = "temporario", "Temporário"
    ESTAGIO = "estagio", "Estágio"


class Situacao(models.TextChoices):
    ATIVO = "ativo", "Ativo"
    AFASTADO = "afastado", "Afastado"
    FERIAS = "ferias", "Férias"
    DESLIGADO = "desligado", "Desligado"


class TipoConta(models.TextChoices):
    CORRENTE = "corrente", "Corrente"
    POUPANCA = "poupanca", "Poupança"
    PAGAMENTO = "pagamento", "Conta de pagamento"


class TipoPix(models.TextChoices):
    CPF = "cpf", "CPF/CNPJ"
    TELEFONE = "telefone", "Telefone"
    EMAIL = "email", "E-mail"
    ALEATORIA = "aleatoria", "Chave aleatória"


DIAS_DA_SEMANA = (
    ("1", "Seg"), ("2", "Ter"), ("3", "Qua"), ("4", "Qui"),
    ("5", "Sex"), ("6", "Sáb"), ("7", "Dom"),
)


# ======================================================================
# COLABORADOR
# ======================================================================
class Colaborador(models.Model):
    """A ficha completa de quem trabalha na fábrica."""

    # ---------------- identificação ----------------
    nome = models.CharField("nome completo", max_length=150)
    cpf = models.CharField("CPF", max_length=11, unique=True, validators=[validar_cpf])
    rg = models.CharField("RG", max_length=20)
    rg_orgao = models.CharField("órgão emissor / UF do RG", max_length=20, blank=True)
    data_nascimento = models.DateField("nascimento")
    pis = models.CharField(
        "PIS/NIS", max_length=11, unique=True, null=True, blank=True,
        validators=[validar_pis],
        help_text="Obrigatório na CLT e no temporário (eSocial).",
    )
    ctps_numero = models.CharField(
        "CTPS (número)", max_length=20, blank=True,
        help_text="Na carteira digital, o número é o CPF.",
    )
    ctps_serie = models.CharField("CTPS (série)", max_length=10, blank=True)
    ctps_uf = models.CharField("CTPS (UF)", max_length=2, blank=True, validators=[validar_uf])

    # ---------------- endereço ----------------
    cep = models.CharField("CEP", max_length=8, validators=[validar_cep])
    logradouro = models.CharField("rua / avenida", max_length=150)
    numero = models.CharField("número", max_length=20)
    complemento = models.CharField(max_length=80, blank=True)
    bairro = models.CharField(max_length=80)
    cidade = models.CharField(max_length=80)
    uf = models.CharField("UF", max_length=2, validators=[validar_uf])

    # ---------------- contato ----------------
    telefone = models.CharField(max_length=11, validators=[validar_telefone])
    email = models.EmailField("e-mail", blank=True)
    emergencia_nome = models.CharField("contato de emergência", max_length=120)
    emergencia_telefone = models.CharField(
        "telefone de emergência", max_length=11, validators=[validar_telefone],
    )
    emergencia_parentesco = models.CharField("parentesco", max_length=40, blank=True)

    # ---------------- trabalho ----------------
    cargo = models.CharField("cargo / função", max_length=80)
    setor = models.CharField(max_length=16, choices=Setor.choices, db_index=True)
    especialidades = models.JSONField(
        default=list, blank=True,
        help_text="Etapas da produção que a pessoa faz (só para a Engenharia de produção).",
    )
    data_admissao = models.DateField("admissão")
    vinculo = models.CharField("vínculo", max_length=12, choices=Vinculo.choices)
    situacao = models.CharField(
        "situação", max_length=12, choices=Situacao.choices, default=Situacao.ATIVO, db_index=True,
    )
    data_desligamento = models.DateField("desligamento", null=True, blank=True)

    # Jornada: é por ela que o espelho de ponto conta atraso, falta e extra.
    jornada_inicio = models.TimeField("entrada da jornada", default=time(8, 0))
    jornada_fim = models.TimeField("saída da jornada", default=time(17, 0))
    jornada_intervalo_min = models.PositiveSmallIntegerField("intervalo (min)", default=60)
    jornada_dias = models.CharField(
        "dias de trabalho", max_length=7, default="12345",
        help_text="Dias da semana, 1 = segunda ... 7 = domingo.",
    )
    # O horário DIA A DIA, como o relógio de ponto (REP) o tem: a sexta que
    # sai uma hora antes, o sábado de meio período. {"1": [["08:00",
    # "12:00"], ["13:00", "18:00"]], ..., "5": [...]} -- dia sem chave é
    # folga. Vazio: vale a jornada simples acima (entrada, saída e
    # intervalo, iguais em todos os dias). Preenchido, ela manda, e os
    # campos simples passam a ser o resumo do dia mais comum.
    jornada_semana = models.JSONField(
        "jornada por dia da semana", default=dict, blank=True,
        help_text="Entradas e saídas de cada dia da semana (o horário do relógio de ponto).",
    )
    matricula = models.CharField(
        "matrícula", max_length=20, blank=True,
        help_text="O número de matrícula no relógio de ponto (REP), se houver.",
    )

    # ---------------- pagamento (Gestão e Financeiro) ----------------
    salario = models.DecimalField("salário", max_digits=10, decimal_places=2, null=True, blank=True)
    banco = models.CharField(max_length=80, blank=True)
    agencia = models.CharField("agência", max_length=10, blank=True)
    conta = models.CharField(max_length=20, blank=True)
    tipo_conta = models.CharField("tipo de conta", max_length=10, choices=TipoConta.choices, blank=True)
    pix_tipo = models.CharField("tipo da chave Pix", max_length=10, choices=TipoPix.choices, blank=True)
    pix_chave = models.CharField("chave Pix", max_length=140, blank=True)

    observacoes = models.TextField("observações", blank=True)

    # ---------------- ligações ----------------
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="colaborador_rh",
        help_text="Conta do painel: quem tem conta bate o ponto e vê as próprias tarefas.",
    )
    colaborador_producao = models.OneToOneField(
        "sistema_interno.Colaborador", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="ficha_rh",
        help_text="O nome desta pessoa nas ordens de produção.",
    )

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
    )

    class Meta:
        verbose_name = "Colaborador (ficha de RH)"
        verbose_name_plural = "Colaboradores (fichas de RH)"
        ordering = ("nome",)

    def __str__(self):
        return self.nome

    # ---------------- normalização e validação ----------------
    CAMPOS_DE_DIGITOS = ("cpf", "pis", "cep", "telefone", "emergencia_telefone")

    def normalizar(self):
        for campo in self.CAMPOS_DE_DIGITOS:
            valor = getattr(self, campo)
            if valor is not None:
                setattr(self, campo, somente_digitos(valor))
        if not self.pis:
            self.pis = None
        for campo in ("uf", "ctps_uf"):
            setattr(self, campo, (getattr(self, campo) or "").strip().upper())
        for campo in ("nome", "rg", "rg_orgao", "logradouro", "numero", "complemento", "bairro",
                      "cidade", "cargo", "emergencia_nome", "emergencia_parentesco", "banco",
                      "agencia", "conta", "pix_chave", "ctps_numero", "ctps_serie"):
            setattr(self, campo, re.sub(r"\s+", " ", getattr(self, campo) or "").strip())
        self.email = (self.email or "").strip().lower()
        self.matricula = re.sub(r"\s+", " ", self.matricula or "").strip()
        self.jornada_semana = normalizar_jornada_semana(self.jornada_semana)
        if self.jornada_semana:
            self._resumir_jornada_semana()
        self.jornada_dias = "".join(sorted(set(re.sub(r"[^1-7]", "", self.jornada_dias or ""))))
        self.especialidades = [e for e in dict.fromkeys(self.especialidades or []) if e in Especialidade.values]

    def _resumir_jornada_semana(self):
        """Os campos simples viram o resumo do horário dia a dia.

        Os dias de trabalho são os que têm horário; entrada, saída e
        intervalo saem do horário mais comum da semana (o de segunda a
        quinta, quando a sexta sai mais cedo).
        """
        try:
            semana = {dia: pares_de_texto(pares) for dia, pares in self.jornada_semana.items()}
        except ValueError:
            return  # a conferência de `clean` diz o que está errado
        contagem = {}
        for dia in sorted(semana):
            contagem.setdefault(tuple(semana[dia]), []).append(dia)
        if not contagem:
            return
        comum = max(contagem, key=lambda pares: (len(contagem[pares]), -int(contagem[pares][0])))
        self.jornada_dias = "".join(sorted(semana))
        self.jornada_inicio = comum[0][0]
        self.jornada_fim = comum[-1][1]
        self.jornada_intervalo_min = sum(
            _minutos(comum[i + 1][0]) - _minutos(comum[i][1]) for i in range(len(comum) - 1)
        )

    def clean(self):
        self.normalizar()
        erros = {}
        hoje = timezone.localdate()

        if self.data_admissao and self.data_admissao > hoje:
            erros["data_admissao"] = "A admissão não pode ser no futuro: cadastre no dia em que a pessoa começar."
        if self.data_nascimento:
            if self.data_nascimento >= hoje:
                erros["data_nascimento"] = "A data de nascimento precisa ser no passado."
            elif idade_em(self.data_nascimento, hoje) > IDADE_MAXIMA:
                erros["data_nascimento"] = "Confira a data de nascimento: passa de 100 anos."
            elif self.data_admissao and self.vinculo in IDADE_MINIMA:
                minima = IDADE_MINIMA[self.vinculo]
                if idade_em(self.data_nascimento, self.data_admissao) < minima:
                    erros["data_nascimento"] = (
                        f"Para {self.get_vinculo_display()}, a pessoa precisa ter ao menos "
                        f"{minima} anos na admissão."
                    )

        if self.situacao == Situacao.DESLIGADO:
            if not self.data_desligamento:
                erros["data_desligamento"] = "Informe a data do desligamento."
        elif self.data_desligamento:
            erros["data_desligamento"] = "A data de desligamento só vale com a situação “Desligado”."
        if self.data_desligamento:
            if self.data_admissao and self.data_desligamento < self.data_admissao:
                erros["data_desligamento"] = "O desligamento não pode ser antes da admissão."
            elif self.data_desligamento > hoje:
                erros["data_desligamento"] = "O desligamento não pode ser no futuro."

        if self.vinculo in (Vinculo.CLT, Vinculo.TEMPORARIO) and not self.pis:
            erros["pis"] = "PIS/NIS é obrigatório para CLT e temporário."

        if self.telefone and self.emergencia_telefone and self.telefone == self.emergencia_telefone:
            erros["emergencia_telefone"] = "O contato de emergência precisa ser de outra pessoa (outro telefone)."

        if self.salario is not None and self.salario < 0:
            erros["salario"] = "O salário não pode ser negativo."

        # ---- jornada ----
        if self.jornada_semana:
            mensagem = erro_da_jornada_semana(self.jornada_semana)
            if mensagem:
                erros["jornada_semana"] = mensagem
        if not self.jornada_dias:
            erros["jornada_dias"] = "Marque ao menos um dia de trabalho."
        if self.jornada_inicio and self.jornada_fim:
            if self.jornada_fim <= self.jornada_inicio:
                erros["jornada_fim"] = "A saída da jornada precisa ser depois da entrada."
            else:
                bruto = _minutos(self.jornada_fim) - _minutos(self.jornada_inicio)
                intervalo = self.jornada_intervalo_min or 0
                liquido = bruto - intervalo
                if intervalo >= bruto:
                    erros["jornada_intervalo_min"] = "O intervalo é maior que a jornada inteira."
                elif liquido > 10 * 60:
                    erros["jornada_fim"] = "A jornada passa de 10 horas por dia (8 h + 2 h extras, o teto da CLT)."
                elif liquido > 6 * 60 and intervalo < 30:
                    erros["jornada_intervalo_min"] = (
                        "Jornada acima de 6 horas pede ao menos 1 hora de intervalo "
                        "(30 minutos só com acordo coletivo)."
                    )

        # ---- Pix ----
        if self.pix_chave and not self.pix_tipo:
            erros["pix_tipo"] = "Escolha o tipo da chave Pix."
        elif self.pix_tipo and not self.pix_chave:
            erros["pix_chave"] = "Informe a chave Pix."
        elif self.pix_chave:
            mensagem = _erro_da_chave_pix(self.pix_tipo, self.pix_chave)
            if mensagem:
                erros["pix_chave"] = mensagem
            elif self.pix_tipo in (TipoPix.CPF, TipoPix.TELEFONE):
                self.pix_chave = somente_digitos(self.pix_chave)
            elif self.pix_tipo == TipoPix.ALEATORIA:
                self.pix_chave = self.pix_chave.lower()

        if erros:
            raise ValidationError(erros)

    def save(self, *args, **kwargs):
        self.normalizar()
        super().save(*args, **kwargs)

    # ---------------- leitura ----------------
    @property
    def cpf_formatado(self):
        return formatar_cpf(self.cpf)

    @property
    def cpf_mascarado(self):
        return mascarar_cpf(self.cpf)

    @property
    def pis_formatado(self):
        return formatar_pis(self.pis or "")

    @property
    def cep_formatado(self):
        return formatar_cep(self.cep)

    @property
    def telefone_formatado(self):
        return formatar_telefone(self.telefone)

    @property
    def emergencia_telefone_formatado(self):
        return formatar_telefone(self.emergencia_telefone)

    @property
    def idade(self):
        return idade_em(self.data_nascimento, timezone.localdate()) if self.data_nascimento else None

    @property
    def primeiro_nome(self):
        return (self.nome or "").split(" ")[0]

    @property
    def iniciais(self):
        partes = [p for p in (self.nome or "").split() if len(p) > 2 or p == (self.nome or "").split()[0]]
        return ((partes[0][:1] if partes else "") + (partes[-1][:1] if len(partes) > 1 else "")).upper() or "?"

    @property
    def endereco_linha(self):
        rua = ", ".join(p for p in (self.logradouro, self.numero) if p)
        if self.complemento:
            rua += f" ({self.complemento})"
        partes = [rua, self.bairro, "/".join(p for p in (self.cidade, self.uf) if p)]
        if self.cep:
            partes.append(f"CEP {self.cep_formatado}")
        return " · ".join(p for p in partes if p)

    @property
    def especialidades_rotulos(self):
        rotulos = dict(Especialidade.choices)
        return [rotulos[e] for e in self.especialidades or [] if e in rotulos]

    @property
    def dias_rotulos(self):
        return " · ".join(rotulo for valor, rotulo in DIAS_DA_SEMANA if valor in (self.jornada_dias or ""))

    @property
    def jornada_minutos(self) -> int:
        """Quanto se trabalha num dia de jornada, já sem o intervalo."""
        if not (self.jornada_inicio and self.jornada_fim):
            return 0
        return max(0, _minutos(self.jornada_fim) - _minutos(self.jornada_inicio) - (self.jornada_intervalo_min or 0))

    @property
    def jornada_texto(self):
        if self.jornada_semana:
            return " · ".join(f"{rotulo} {texto}" for rotulo, texto in self.jornada_por_grupo)
        return (
            f"{self.jornada_inicio:%H:%M}–{self.jornada_fim:%H:%M}, "
            f"intervalo {self.jornada_intervalo_min} min · {self.dias_rotulos}"
        )

    # ---------------- o horário de cada dia ----------------
    def pares_do_dia(self, dia: date) -> list:
        """[(entrada, saída), ...] previstos no dia (vazio: não trabalha)."""
        chave = str(dia.isoweekday())
        if self.jornada_semana:
            try:
                return pares_de_texto(self.jornada_semana.get(chave) or [])
            except ValueError:
                return []
        if chave not in (self.jornada_dias or "") or not (self.jornada_inicio and self.jornada_fim):
            return []
        return [(self.jornada_inicio, self.jornada_fim)]

    def minutos_previstos(self, dia: date) -> int:
        if not self.jornada_semana:
            return self.jornada_minutos if self.trabalha_no_dia(dia) else 0
        return sum(_minutos(fim) - _minutos(inicio) for inicio, fim in self.pares_do_dia(dia))

    def inicio_previsto(self, dia: date):
        pares = self.pares_do_dia(dia)
        return pares[0][0] if pares else self.jornada_inicio

    def fim_previsto(self, dia: date):
        pares = self.pares_do_dia(dia)
        return pares[-1][1] if pares else self.jornada_fim

    @property
    def jornada_por_grupo(self) -> list:
        """[("Seg a Qui", "08:00–12:00 · 13:00–18:00"), ("Sex", "...")]: os dias iguais juntos."""
        grupos = []
        for valor, rotulo in DIAS_DA_SEMANA:
            if self.jornada_semana:
                try:
                    pares = pares_de_texto(self.jornada_semana.get(valor) or [])
                except ValueError:
                    pares = []
            else:
                pares = [(self.jornada_inicio, self.jornada_fim)] if valor in (self.jornada_dias or "") else []
            if not pares:
                continue
            texto = " · ".join(f"{a:%H:%M}–{b:%H:%M}" for a, b in pares)
            if grupos and grupos[-1][2] == texto and int(grupos[-1][1]) == int(valor) - 1:
                grupos[-1] = (grupos[-1][0], valor, texto, grupos[-1][3] + [rotulo])
            else:
                grupos.append((valor, valor, texto, [rotulo]))
        saida = []
        for _, _, texto, rotulos in grupos:
            nome = rotulos[0] if len(rotulos) == 1 else (
                f"{rotulos[0]} e {rotulos[1]}" if len(rotulos) == 2 else f"{rotulos[0]} a {rotulos[-1]}"
            )
            if not self.jornada_semana:
                texto += f" (intervalo {self.jornada_intervalo_min} min)"
            saida.append((nome, texto))
        return saida

    @property
    def horas_semanais(self) -> str:
        total = sum(self.minutos_previstos(date(2024, 1, d)) for d in range(1, 8))  # 1/1/2024 é segunda
        horas, minutos = divmod(total, 60)
        return f"{horas}h{minutos:02d}" if minutos else f"{horas}h"

    def trabalha_no_dia(self, dia: date) -> bool:
        if self.jornada_semana:
            return bool(self.pares_do_dia(dia))
        return str(dia.isoweekday()) in (self.jornada_dias or "")

    def empregado_em(self, dia: date) -> bool:
        if self.data_admissao and dia < self.data_admissao:
            return False
        if self.data_desligamento and dia > self.data_desligamento:
            return False
        return True

    @property
    def pode_bater_ponto(self) -> bool:
        return self.situacao == Situacao.ATIVO

    @property
    def tem_pagamento(self) -> bool:
        return bool(self.pix_chave or (self.banco and self.conta))

    @property
    def pix_chave_formatada(self):
        if self.pix_tipo == TipoPix.TELEFONE:
            return formatar_telefone(self.pix_chave)
        if self.pix_tipo == TipoPix.CPF and len(self.pix_chave) == 11:
            return formatar_cpf(self.pix_chave)
        return self.pix_chave


def _minutos(hora: time) -> int:
    return hora.hour * 60 + hora.minute


# ---------------- a jornada dia a dia (Colaborador.jornada_semana) ----------------
def _hora_de_texto(texto) -> time:
    if isinstance(texto, time):
        return texto
    achado = re.fullmatch(r"\s*(\d{1,2}):(\d{2})\s*", str(texto or ""))
    if not achado:
        raise ValueError(f"hora inválida: {texto!r}")
    hora, minuto = int(achado.group(1)), int(achado.group(2))
    if hora > 23 or minuto > 59:
        raise ValueError(f"hora inválida: {texto!r}")
    return time(hora, minuto)


def pares_de_texto(pares) -> list:
    """[["08:00", "12:00"], ...] -> [(time, time), ...]. Levanta ValueError."""
    saida = []
    for par in pares or []:
        if not isinstance(par, (list, tuple)) or len(par) != 2:
            raise ValueError("cada período tem entrada e saída")
        saida.append((_hora_de_texto(par[0]), _hora_de_texto(par[1])))
    return saida


def normalizar_jornada_semana(semana) -> dict:
    """Só os dias com horário, chaves "1".."7", horas em "HH:MM"."""
    if not isinstance(semana, dict):
        return {}
    limpo = {}
    for chave, pares in semana.items():
        chave = str(chave).strip()
        if chave not in {"1", "2", "3", "4", "5", "6", "7"} or not pares:
            continue
        try:
            limpo[chave] = [[f"{a:%H:%M}", f"{b:%H:%M}"] for a, b in pares_de_texto(pares)]
        except ValueError:
            limpo[chave] = pares  # fica como veio: `erro_da_jornada_semana` explica
    return dict(sorted(limpo.items()))


def erro_da_jornada_semana(semana) -> str:
    """A mesma regra da jornada simples, dia por dia (CLT, arts. 58 e 71)."""
    nomes = dict(DIAS_DA_SEMANA)
    for chave, pares in sorted((semana or {}).items()):
        nome = nomes.get(chave, chave)
        try:
            periodos = pares_de_texto(pares)
        except ValueError:
            return f"{nome}: confira as horas (formato 08:00)."
        anterior_fim = None
        for inicio, fim in periodos:
            if fim <= inicio:
                return f"{nome}: a saída das {fim:%H:%M} precisa ser depois da entrada das {inicio:%H:%M}."
            if anterior_fim is not None and inicio < anterior_fim:
                return f"{nome}: os períodos se sobrepõem ({anterior_fim:%H:%M} e {inicio:%H:%M})."
            anterior_fim = fim
        liquido = sum(_minutos(b) - _minutos(a) for a, b in periodos)
        intervalo = sum(_minutos(periodos[i + 1][0]) - _minutos(periodos[i][1]) for i in range(len(periodos) - 1))
        if liquido > 10 * 60:
            return f"{nome}: passa de 10 horas de trabalho (8 h + 2 h extras, o teto da CLT)."
        if liquido > 6 * 60 and intervalo < 30:
            return f"{nome}: jornada acima de 6 horas pede intervalo (ao menos 1 hora; 30 minutos só com acordo coletivo)."
    return ""


def _erro_da_chave_pix(tipo, chave) -> str:
    chave = (chave or "").strip()
    if tipo == TipoPix.CPF:
        numero = somente_digitos(chave)
        if not (cpf_valido(numero) or (len(numero) == 14 and cnpj_valido(numero))):
            return "A chave Pix do tipo CPF/CNPJ precisa ser um CPF ou CNPJ válido."
    elif tipo == TipoPix.TELEFONE:
        if not telefone_valido(chave):
            return "A chave Pix do tipo telefone precisa ter DDD + número."
    elif tipo == TipoPix.EMAIL:
        try:
            validate_email(chave)
        except ValidationError:
            return "A chave Pix do tipo e-mail precisa ser um e-mail válido."
    elif tipo == TipoPix.ALEATORIA:
        if not re.fullmatch(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", chave):
            return "A chave aleatória tem 32 letras e números em 5 grupos (formato 1234abcd-...)."
    return ""


# ======================================================================
# DOCUMENTOS
# ======================================================================
class TipoDocumento(models.TextChoices):
    RG_CNH = "rg_cnh", "RG ou CNH"
    CPF = "cpf", "CPF"
    RESIDENCIA = "residencia", "Comprovante de residência"
    CTPS = "ctps", "Carteira de trabalho (CTPS)"
    CERTIDAO = "certidao", "Certidão de nascimento ou casamento"
    ASO = "aso", "ASO (exame admissional ou periódico)"
    CONTRATO = "contrato", "Contrato"
    MATRICULA = "matricula", "Declaração de matrícula (estágio)"
    CURRICULO = "curriculo", "Histórico / currículo"
    TERMO = "termo", "Termo de exclusividade (assinado)"
    CARTAO_PONTO = "cartao_ponto", "Cartão de ponto (relógio REP)"
    OUTRO = "outro", "Outro documento"


#: O que cada vínculo precisa ter na pasta. É a lista que a ficha mostra
#: como checklist ("o que FALTA").
OBRIGATORIOS = {
    Vinculo.CLT: (
        TipoDocumento.RG_CNH, TipoDocumento.CPF, TipoDocumento.RESIDENCIA, TipoDocumento.CTPS,
        TipoDocumento.CERTIDAO, TipoDocumento.ASO, TipoDocumento.CONTRATO,
    ),
    Vinculo.TEMPORARIO: (
        TipoDocumento.RG_CNH, TipoDocumento.CPF, TipoDocumento.RESIDENCIA, TipoDocumento.CTPS,
        TipoDocumento.ASO, TipoDocumento.CONTRATO,
    ),
    Vinculo.PJ: (
        TipoDocumento.RG_CNH, TipoDocumento.CPF, TipoDocumento.RESIDENCIA, TipoDocumento.CONTRATO,
    ),
    Vinculo.ESTAGIO: (
        TipoDocumento.RG_CNH, TipoDocumento.CPF, TipoDocumento.RESIDENCIA,
        TipoDocumento.MATRICULA, TipoDocumento.CONTRATO,
    ),
}

#: Documentos que vencem: a validade é obrigatória neles.
COM_VALIDADE_OBRIGATORIA = (TipoDocumento.ASO, TipoDocumento.MATRICULA)

#: Comprovante de residência mais velho que isso é sinalizado (não barrado).
RESIDENCIA_RECENTE_DIAS = 90


def caminho_do_documento(instancia, nome_arquivo):
    """Nome aleatório, sem nome nem CPF de ninguém no caminho do arquivo."""
    import uuid

    extensao = ""
    if "." in (nome_arquivo or ""):
        extensao = "." + nome_arquivo.rsplit(".", 1)[-1].lower()
    if extensao not in (".pdf", ".jpg", ".png", ".webp"):
        extensao = ".bin"
    aleatorio = uuid.uuid4().hex
    return f"rh/{aleatorio[:2]}/{aleatorio}{extensao}"


class DocumentoColaborador(models.Model):
    colaborador = models.ForeignKey(Colaborador, on_delete=models.CASCADE, related_name="documentos")
    tipo = models.CharField(max_length=12, choices=TipoDocumento.choices, db_index=True)
    descricao = models.CharField("descrição", max_length=120, blank=True)
    arquivo = models.FileField(upload_to=caminho_do_documento, storage=armazenamento_privado, max_length=200)
    nome_original = models.CharField(max_length=150, blank=True)
    tipo_conteudo = models.CharField(max_length=40)
    tamanho = models.PositiveIntegerField(default=0)
    sha256 = models.CharField(max_length=64)
    emissao = models.DateField("emissão", null=True, blank=True)
    validade = models.DateField(null=True, blank=True, db_index=True)
    enviado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
    )
    enviado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Documento do colaborador"
        verbose_name_plural = "Documentos dos colaboradores"
        ordering = ("-enviado_em", "-id")

    def __str__(self):
        return f"{self.get_tipo_display()} · {self.colaborador}"

    def clean(self):
        erros = {}
        hoje = timezone.localdate()
        if self.emissao and self.emissao > hoje:
            erros["emissao"] = "A emissão não pode ser no futuro."
        if self.validade and self.emissao and self.validade < self.emissao:
            erros["validade"] = "A validade não pode ser antes da emissão."
        if self.tipo in COM_VALIDADE_OBRIGATORIA and not self.validade:
            erros["validade"] = f"{self.get_tipo_display()} vence: informe a validade."
        if self.tipo == TipoDocumento.OUTRO and not (self.descricao or "").strip():
            erros["descricao"] = "Diga que documento é este."
        if erros:
            raise ValidationError(erros)

    @property
    def rotulo(self):
        return self.descricao or self.get_tipo_display()

    @property
    def vencido(self):
        return bool(self.validade and self.validade < timezone.localdate())

    @property
    def dias_para_vencer(self):
        if not self.validade:
            return None
        return (self.validade - timezone.localdate()).days

    @property
    def residencia_antiga(self):
        return bool(
            self.tipo == TipoDocumento.RESIDENCIA and self.emissao
            and (timezone.localdate() - self.emissao).days > RESIDENCIA_RECENTE_DIAS
        )

    @property
    def tamanho_texto(self):
        if self.tamanho >= 1024 * 1024:
            return f"{self.tamanho / (1024 * 1024):.1f} MB".replace(".", ",")
        return f"{max(1, round(self.tamanho / 1024))} KB"

    @property
    def eh_pdf(self):
        return self.tipo_conteudo == "application/pdf"


# ======================================================================
# TRILHA DE AUDITORIA
# ======================================================================
class RegistroRH(models.Model):
    """Quem fez o quê com dado pessoal: abriu documento, imprimiu ficha...

    Só se acrescenta. A linha não se edita nem se apaga pela aplicação; o
    colaborador ou o documento apagados ficam como texto na descrição.
    """

    class Acao(models.TextChoices):
        DOC_ABERTO = "doc_aberto", "Abriu documento"
        DOC_ENVIADO = "doc_enviado", "Enviou documento"
        DOC_REMOVIDO = "doc_removido", "Removeu documento"
        FICHA_CRIADA = "ficha_criada", "Cadastrou colaborador"
        FICHA_ALTERADA = "ficha_alterada", "Alterou a ficha"
        FICHA_IMPRESSA = "ficha_impressa", "Gerou a ficha em PDF"
        ESPELHO_IMPRESSO = "espelho_impresso", "Gerou o espelho de ponto"
        AJUSTE_DECIDIDO = "ajuste_decidido", "Decidiu ajuste de ponto"
        ACESSO_NEGADO = "acesso_negado", "Tentou abrir sem permissão"
        CARTAO_ENVIADO = "cartao_enviado", "Enviou cartão de ponto (PDF)"
        CARTAO_IMPORTADO = "cartao_importado", "Importou cartão de ponto"
        CARTAO_DESCARTADO = "cartao_descartado", "Descartou cartão de ponto"

    momento = models.DateTimeField(auto_now_add=True, db_index=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
    )
    usuario_nome = models.CharField(max_length=150, blank=True)
    acao = models.CharField(max_length=20, choices=Acao.choices, db_index=True)
    colaborador = models.ForeignKey(
        Colaborador, on_delete=models.SET_NULL, null=True, blank=True, related_name="registros",
    )
    documento = models.ForeignKey(
        DocumentoColaborador, on_delete=models.SET_NULL, null=True, blank=True, related_name="acessos",
    )
    descricao = models.CharField(max_length=300, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    navegador = models.CharField(max_length=300, blank=True)

    class Meta:
        verbose_name = "Registro de RH (auditoria)"
        verbose_name_plural = "Registros de RH (auditoria)"
        ordering = ("-momento", "-id")

    def __str__(self):
        return f"{self.momento:%d/%m/%Y %H:%M} · {self.usuario_nome} · {self.get_acao_display()}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RegistroImutavel("Registro de auditoria não se edita.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RegistroImutavel("Registro de auditoria não se apaga.")


# ======================================================================
# PONTO
# ======================================================================
class TipoMarcacao(models.TextChoices):
    ENTRADA = "entrada", "Entrada"
    SAIDA_INTERVALO = "saida_intervalo", "Saída para intervalo"
    VOLTA_INTERVALO = "volta_intervalo", "Volta do intervalo"
    SAIDA = "saida", "Saída"


class OrigemMarcacao(models.TextChoices):
    REP = "rep", "Relógio REP-P (importado do cartão de ponto)"


#: A legenda do cartão de ponto do relógio (Control iD, REP-P).
MARCADORES_REP = {
    "I": "Incluído",
    "P": "Pré-assinalado",
    "M": "Coletor REP-P Mobile/Web",
    "C": "Coletor REP-P (iDFace/iDFlex)",
}


def caminho_do_cartao(instancia, nome_arquivo):
    """Nome aleatório, como o dos documentos: nada de nome ou CPF no caminho."""
    import uuid

    aleatorio = uuid.uuid4().hex
    return f"rh/cartoes/{aleatorio[:2]}/{aleatorio}.pdf"


class ImportacaoPonto(models.Model):
    """Um PDF de cartão de ponto enviado ao RH -- pode trazer várias pessoas.

    O arquivo original fica no armazenamento privado (sem endereço; só a
    Gestão abre, pela view, e fica na trilha). Cada pessoa achada nele é um
    `CartaoPonto`. O mesmo arquivo (SHA-256) não entra duas vezes.
    """

    arquivo = models.FileField(upload_to=caminho_do_cartao, storage=armazenamento_privado, max_length=200)
    nome_original = models.CharField(max_length=150, blank=True)
    tamanho = models.PositiveIntegerField(default=0)
    sha256 = models.CharField(max_length=64, unique=True)
    paginas = models.PositiveSmallIntegerField(default=0)
    empresa_nome = models.CharField(max_length=160, blank=True)
    empresa_cnpj = models.CharField(max_length=14, blank=True)
    cnpj_confere = models.BooleanField(default=True)
    avisos = models.JSONField(default=list, blank=True)
    enviado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
    )
    enviado_em = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Cartão de ponto enviado (PDF)"
        verbose_name_plural = "Cartões de ponto enviados (PDF)"
        ordering = ("-enviado_em", "-id")

    def __str__(self):
        return f"{self.nome_original or 'cartão de ponto'} · {timezone.localtime(self.enviado_em):%d/%m/%Y %H:%M}"

    @property
    def tamanho_texto(self):
        if self.tamanho >= 1024 * 1024:
            return f"{self.tamanho / (1024 * 1024):.1f} MB".replace(".", ",")
        return f"{max(1, round(self.tamanho / 1024))} KB"


class CartaoPonto(models.Model):
    """O cartão de UMA pessoa, lido de um PDF (rh/cartao_ponto.py).

    Pendente: lido, conferido, esperando o "Importar" (ou o cadastro de
    quem não tem ficha). Importado: as marcações entraram no ponto (com
    a origem "rep"), os campos vazios da ficha foram preenchidos e o PDF
    da pessoa foi para a pasta dela. `dados` guarda a leitura inteira
    (dias, marcas, totais do cartão); `resultado`, o que a importação fez.
    """

    class Estado(models.TextChoices):
        PENDENTE = "pendente", "Esperando importar"
        IMPORTADO = "importado", "Importado"
        DESCARTADO = "descartado", "Descartado"

    importacao = models.ForeignKey(ImportacaoPonto, on_delete=models.CASCADE, related_name="cartoes")
    ordem = models.PositiveSmallIntegerField(default=1)
    colaborador = models.ForeignKey(
        Colaborador, on_delete=models.SET_NULL, null=True, blank=True, related_name="cartoes_ponto",
    )
    casado_por = models.CharField(max_length=4, blank=True, help_text="cpf ou pis: nunca pelo nome.")
    nome = models.CharField(max_length=150)
    cpf = models.CharField(max_length=11, blank=True)
    pis = models.CharField(max_length=11, blank=True)
    inicio = models.DateField(db_index=True)
    fim = models.DateField()
    dados = models.JSONField()
    situacao = models.CharField(max_length=10, choices=Estado.choices, default=Estado.PENDENTE, db_index=True)
    resultado = models.JSONField(default=dict, blank=True)
    documento = models.OneToOneField(
        DocumentoColaborador, on_delete=models.SET_NULL, null=True, blank=True, related_name="cartao_ponto",
    )
    importado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
    )
    importado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Cartão de ponto (uma pessoa)"
        verbose_name_plural = "Cartões de ponto (uma pessoa)"
        ordering = ("-inicio", "importacao_id", "ordem")
        indexes = [models.Index(fields=("colaborador", "inicio"), name="rh_cartao_periodo")]

    def __str__(self):
        return f"Cartão {self.inicio:%d/%m}–{self.fim:%d/%m/%Y} · {self.nome}"

    @property
    def importado(self):
        return self.situacao == self.Estado.IMPORTADO

    @property
    def pendente(self):
        return self.situacao == self.Estado.PENDENTE

    @property
    def periodo_texto(self):
        if self.inicio.year == self.fim.year:
            return f"{self.inicio:%d/%m} a {self.fim:%d/%m/%Y}"
        return f"{self.inicio:%d/%m/%Y} a {self.fim:%d/%m/%Y}"

    @property
    def cpf_mascarado(self):
        return mascarar_cpf(self.cpf) if self.cpf else "—"


class MarcacaoQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise RegistroImutavel("Marcação de ponto não se edita: peça um ajuste.")

    def delete(self):
        raise RegistroImutavel("Marcação de ponto não se apaga: peça um ajuste.")

    # O caminho em massa também não passa.
    def bulk_update(self, *args, **kwargs):
        raise RegistroImutavel("Marcação de ponto não se edita: peça um ajuste.")


class MarcacaoPonto(models.Model):
    """Uma batida de ponto. Escrita uma vez, com a hora do servidor."""

    colaborador = models.ForeignKey(Colaborador, on_delete=models.PROTECT, related_name="marcacoes")
    nsr = models.PositiveIntegerField(
        "NSR", help_text="Número sequencial do registro, por colaborador (1, 2, 3...).",
    )
    tipo = models.CharField(max_length=16, choices=TipoMarcacao.choices)
    momento = models.DateTimeField("data e hora (servidor)", default=timezone.now, editable=False)
    data = models.DateField(db_index=True, editable=False)
    ip = models.GenericIPAddressField(null=True, blank=True, editable=False)
    navegador = models.CharField(max_length=300, blank=True, editable=False)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, editable=False)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, editable=False)
    precisao_m = models.PositiveIntegerField("precisão (m)", null=True, blank=True, editable=False)
    hash_anterior = models.CharField(max_length=64, blank=True, editable=False)
    hash = models.CharField(max_length=64, unique=True, editable=False)
    # DE ONDE VEIO. Vazio (NULL) é o painel (celular ou PC, a hora do
    # servidor). "rep" é o relógio de ponto, importado do cartão de ponto em
    # PDF (rh/importacao_ponto.py), com a marca que o relógio pôs ao lado
    # da hora: (I) incluído, (P) pré-assinalado, (M) coletor mobile/web,
    # (C) coletor iDFace/iDFlex. Colunas que aceitam NULL de propósito: no
    # SQLite, coluna nova sem padrão entra por ALTER TABLE ADD COLUMN, sem
    # recriar a tabela -- recriar perderia o gatilho que proíbe UPDATE e
    # DELETE (migração 0002). Entram no hash quando preenchidas.
    origem = models.CharField(
        max_length=8, choices=OrigemMarcacao.choices, null=True, blank=True, editable=False,
    )
    marcador = models.CharField(max_length=1, null=True, blank=True, editable=False)
    cartao = models.ForeignKey(
        "CartaoPonto", on_delete=models.PROTECT, null=True, blank=True, editable=False,
        related_name="marcacoes",
    )

    objects = MarcacaoQuerySet.as_manager()

    class Meta:
        verbose_name = "Marcação de ponto"
        verbose_name_plural = "Marcações de ponto"
        ordering = ("momento", "id")
        constraints = [
            models.UniqueConstraint(fields=("colaborador", "nsr"), name="rh_marcacao_nsr_unico"),
        ]
        indexes = [models.Index(fields=("colaborador", "data"), name="rh_marcacao_dia")]

    def __str__(self):
        return f"{self.get_tipo_display()} · {self.colaborador} · {timezone.localtime(self.momento):%d/%m/%Y %H:%M}"

    def calcular_hash(self) -> str:
        """A impressão digital da marcação, presa à anterior do colaborador.

        Mudar qualquer coisa -- a hora, o tipo, o IP, a ordem -- muda este
        hash e quebra o elo com a marcação seguinte. `ponto.conferir_cadeia`
        refaz a conta inteira.
        """
        momento = self.momento.astimezone(dt_timezone.utc)
        partes = [
            self.hash_anterior or "",
            str(self.colaborador_id),
            str(self.nsr),
            self.tipo,
            momento.strftime("%Y-%m-%dT%H:%M:%S.%f"),
            self.ip or "",
            _texto_decimal(self.latitude),
            _texto_decimal(self.longitude),
            str(self.precisao_m or ""),
        ]
        if self.origem:
            # A origem também é selada (as marcações do painel, sem origem,
            # mantêm o hash de antes).
            partes += [f"origem={self.origem}", self.marcador or "", str(self.cartao_id or "")]
        return hashlib.sha256("|".join(partes).encode("utf-8")).hexdigest()

    @property
    def do_relogio(self) -> bool:
        return self.origem == OrigemMarcacao.REP

    @property
    def origem_rotulo(self) -> str:
        if not self.origem:
            return "Painel (celular ou PC)"
        rotulo = OrigemMarcacao(self.origem).label
        if self.marcador:
            rotulo += f" · ({self.marcador}) {MARCADORES_REP.get(self.marcador, 'marca do relógio')}"
        return rotulo

    @property
    def codigo(self) -> str:
        """O código do comprovante: o começo do hash, em três grupos."""
        base = (self.hash or "")[:12].upper()
        return "-".join(base[i:i + 4] for i in range(0, len(base), 4))

    @property
    def hora_local(self):
        return timezone.localtime(self.momento)

    @property
    def tem_localizacao(self):
        return self.latitude is not None and self.longitude is not None

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RegistroImutavel("Marcação de ponto não se edita: peça um ajuste.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RegistroImutavel("Marcação de ponto não se apaga: peça um ajuste.")


def _texto_decimal(valor) -> str:
    if valor is None:
        return ""
    return str(Decimal(valor).quantize(Decimal("0.000001")))


class AjustePonto(models.Model):
    """A correção do ponto: um registro À PARTE, que nunca mexe na marcação."""

    class Tipo(models.TextChoices):
        INCLUIR = "incluir", "Incluir marcação esquecida"
        DESCONSIDERAR = "desconsiderar", "Desconsiderar marcação errada"
        ABONO = "abono", "Abonar o dia"

    class Motivo(models.TextChoices):
        ATESTADO = "atestado", "Atestado médico"
        FERIAS = "ferias", "Férias"
        FOLGA = "folga", "Folga / compensação"
        FERIADO = "feriado", "Feriado local"
        OUTRO = "outro", "Outro motivo"

    class Estado(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        APROVADO = "aprovado", "Aprovado"
        RECUSADO = "recusado", "Recusado"

    colaborador = models.ForeignKey(Colaborador, on_delete=models.PROTECT, related_name="ajustes")
    tipo = models.CharField(max_length=14, choices=Tipo.choices)
    data = models.DateField("dia", db_index=True)
    hora = models.TimeField(null=True, blank=True)
    tipo_marcacao = models.CharField(max_length=16, choices=TipoMarcacao.choices, blank=True)
    marcacao = models.ForeignKey(
        MarcacaoPonto, on_delete=models.PROTECT, null=True, blank=True, related_name="ajustes",
    )
    motivo_abono = models.CharField(max_length=10, choices=Motivo.choices, blank=True)
    justificativa = models.TextField()
    situacao = models.CharField(
        max_length=10, choices=Estado.choices, default=Estado.PENDENTE, db_index=True,
    )
    solicitado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
    )
    solicitado_em = models.DateTimeField(auto_now_add=True)
    decidido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
    )
    decidido_em = models.DateTimeField(null=True, blank=True)
    resposta = models.TextField(blank=True)

    class Meta:
        verbose_name = "Ajuste de ponto"
        verbose_name_plural = "Ajustes de ponto"
        ordering = ("-solicitado_em", "-id")

    def __str__(self):
        return f"{self.get_tipo_display()} · {self.colaborador} · {self.data:%d/%m/%Y}"

    def clean(self):
        erros = {}
        hoje = timezone.localdate()
        if len((self.justificativa or "").strip()) < 10:
            erros["justificativa"] = "Explique o motivo (ao menos 10 letras): é o que a Gestão vai ler."
        if self.data and self.data > hoje and self.tipo != self.Tipo.ABONO:
            erros["data"] = "Só se ajusta dia que já aconteceu."
        if self.data and self.tipo == self.Tipo.ABONO and self.data > hoje + timedelta(days=90):
            erros["data"] = "Abono com mais de 90 dias de antecedência: lance mais perto da data."
        colaborador = self.colaborador if self.colaborador_id else None
        if colaborador and self.data and colaborador.data_admissao and self.data < colaborador.data_admissao:
            erros["data"] = "Esse dia é antes da admissão."

        if self.tipo == self.Tipo.INCLUIR:
            if not self.hora:
                erros["hora"] = "Informe a hora da marcação esquecida."
            if not self.tipo_marcacao:
                erros["tipo_marcacao"] = "Diga qual marcação faltou (entrada, saída...)."
            if self.data == hoje and self.hora and self.hora > timezone.localtime().time():
                erros["hora"] = "Essa hora ainda não chegou."
        elif self.tipo == self.Tipo.DESCONSIDERAR:
            if not self.marcacao_id:
                erros["marcacao"] = "Escolha a marcação errada."
            elif colaborador and self.marcacao.colaborador_id != colaborador.pk:
                erros["marcacao"] = "Essa marcação é de outra pessoa."
            else:
                self.data = self.marcacao.data
                repetido = AjustePonto.objects.filter(
                    marcacao_id=self.marcacao_id,
                    situacao__in=(self.Estado.PENDENTE, self.Estado.APROVADO),
                ).exclude(pk=self.pk)
                if repetido.exists():
                    erros["marcacao"] = "Já existe um pedido para desconsiderar essa marcação."
        elif self.tipo == self.Tipo.ABONO:
            if not self.motivo_abono:
                erros["motivo_abono"] = "Escolha o motivo do abono."
        if erros:
            raise ValidationError(erros)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            atual = AjustePonto.objects.filter(pk=self.pk).values_list("situacao", flat=True).first()
            if atual and atual != self.Estado.PENDENTE:
                raise RegistroImutavel("Ajuste já decidido não muda: peça outro ajuste.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.situacao != self.Estado.PENDENTE:
            raise RegistroImutavel("Ajuste decidido fica no histórico.")
        super().delete(*args, **kwargs)

    @property
    def resumo(self):
        if self.tipo == self.Tipo.INCLUIR:
            return f"Incluir {self.get_tipo_marcacao_display().lower()} às {self.hora:%H:%M}"
        if self.tipo == self.Tipo.DESCONSIDERAR and self.marcacao_id:
            return (
                f"Desconsiderar {self.marcacao.get_tipo_display().lower()} das "
                f"{self.marcacao.hora_local:%H:%M}"
            )
        return f"Abonar o dia · {self.get_motivo_abono_display()}"


# ======================================================================
# TAREFAS
# ======================================================================
class Tarefa(models.Model):
    """Uma tarefa de alguém: avulsa, ou ligada a uma coisa do sistema.

    A ligação é genérica (`objeto`): uma etapa da produção, um pedido, uma
    O.S. -- sem o RH depender do código de quem a cria. Uma coisa + etapa
    tem no máximo UMA tarefa (atribuir de novo troca o responsável). Ver
    `tarefas.atribuir`.
    """

    class Prioridade(models.TextChoices):
        BAIXA = "baixa", "Baixa"
        NORMAL = "normal", "Normal"
        ALTA = "alta", "Alta"
        URGENTE = "urgente", "Urgente"

    class Estado(models.TextChoices):
        A_FAZER = "a_fazer", "A fazer"
        FAZENDO = "fazendo", "Fazendo"
        FEITA = "feita", "Feita"

    titulo = models.CharField("título", max_length=160)
    descricao = models.TextField("descrição", blank=True)
    prazo = models.DateField(null=True, blank=True, db_index=True)
    prioridade = models.CharField(max_length=8, choices=Prioridade.choices, default=Prioridade.NORMAL)
    situacao = models.CharField(
        "situação", max_length=8, choices=Estado.choices, default=Estado.A_FAZER, db_index=True,
    )
    colaborador = models.ForeignKey(
        Colaborador, on_delete=models.SET_NULL, null=True, blank=True, related_name="tarefas",
    )
    setor = models.CharField(max_length=16, choices=Setor.choices, blank=True)
    etapa = models.CharField(max_length=60, blank=True)

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveBigIntegerField(null=True, blank=True)
    objeto = GenericForeignKey("content_type", "object_id")
    origem_rotulo = models.CharField("de onde vem", max_length=200, blank=True)
    origem_url = models.CharField(max_length=300, blank=True)

    criada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
    )
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)
    iniciada_em = models.DateTimeField(null=True, blank=True)
    concluida_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Tarefa"
        verbose_name_plural = "Tarefas"
        ordering = ("situacao", "prazo", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("content_type", "object_id", "etapa"),
                condition=Q(content_type__isnull=False),
                name="rh_tarefa_uma_por_etapa",
            ),
        ]
        indexes = [models.Index(fields=("colaborador", "situacao"), name="rh_tarefa_de_quem")]

    def __str__(self):
        return self.titulo

    def clean(self):
        erros = {}
        if not (self.titulo or "").strip():
            erros["titulo"] = "Dê um título à tarefa."
        if self.prazo and not self.pk and self.prazo < timezone.localdate():
            erros["prazo"] = "O prazo não pode ser no passado."
        if self.colaborador_id and self.colaborador.situacao == Situacao.DESLIGADO:
            erros["colaborador"] = "Essa pessoa foi desligada: escolha outra."
        if erros:
            raise ValidationError(erros)

    @property
    def atrasada(self):
        return bool(
            self.prazo and self.situacao != self.Estado.FEITA and self.prazo < timezone.localdate()
        )

    @property
    def da_producao(self):
        return bool(self.content_type_id)

    def mudar_situacao(self, nova):
        if nova not in self.Estado.values:
            raise ValidationError("Situação inválida.")
        agora = timezone.now()
        if nova == self.Estado.FAZENDO and not self.iniciada_em:
            self.iniciada_em = agora
        if nova == self.Estado.FEITA:
            self.concluida_em = agora
            if not self.iniciada_em:
                self.iniciada_em = agora
        else:
            self.concluida_em = None
        self.situacao = nova


# ======================================================================
# TERMO DE EXCLUSIVIDADE E CONFIDENCIALIDADE
# ======================================================================
class TermoExclusividade(models.Model):
    """O termo que o colaborador assina: não trabalhar para o ramo de fora.

    O mesmo desenho do termo de compra do orçamento (`DocumentoAssinatura`):
    o texto é CONGELADO num JSON na hora de gerar (o retrato) e o SHA-256
    dele vai para a trilha; a assinatura grava o traço, a data, o IP, o
    aparelho e o hash conferido naquele instante; assinado, não muda mais.
    O PDF assinado vira um documento do colaborador (armazenamento privado).

    A situação, para o colaborador: PENDENTE (nenhum termo da versão atual
    do texto), ENVIADO (gerado, esperando a assinatura) e ASSINADO. Quando
    o texto muda, a versão (`rh.termo.VERSAO_DO_TERMO`) sobe e todo mundo
    volta a "pendente": o termo antigo continua guardado, mas não vale para
    o texto novo.
    """

    class Estado(models.TextChoices):
        ENVIADO = "enviado", "Enviado para assinatura"
        ASSINADO = "assinado", "Assinado"
        SUBSTITUIDO = "substituido", "Substituído"

    class Canal(models.TextChoices):
        PAINEL = "painel", "No painel, com a conta da pessoa"
        LINK = "link", "Pelo link do celular"

    colaborador = models.ForeignKey(Colaborador, on_delete=models.PROTECT, related_name="termos")
    versao = models.CharField("versão do texto", max_length=20, db_index=True)
    conteudo = models.JSONField("retrato do termo")
    hash_conteudo = models.CharField("SHA-256 do retrato", max_length=64)
    situacao = models.CharField(
        "situação", max_length=12, choices=Estado.choices, default=Estado.ENVIADO, db_index=True,
    )
    gerado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
    )
    gerado_em = models.DateTimeField(auto_now_add=True)
    links_gerados = models.PositiveIntegerField(default=0)
    ultimo_link_em = models.DateTimeField(null=True, blank=True)

    assinado_em = models.DateTimeField(null=True, blank=True)
    assinante_nome = models.CharField(max_length=160, blank=True)
    assinante_cpf = models.CharField(max_length=11, blank=True)
    assinatura_png = models.BinaryField(null=True, blank=True, editable=False)
    assinatura_ip = models.GenericIPAddressField(null=True, blank=True)
    assinatura_navegador = models.CharField(max_length=400, blank=True)
    hash_assinado = models.CharField(max_length=64, blank=True)
    canal = models.CharField(max_length=8, choices=Canal.choices, blank=True)
    documento = models.OneToOneField(
        DocumentoColaborador, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="termo", help_text="O PDF assinado, na pasta do colaborador.",
    )

    class Meta:
        verbose_name = "Termo de exclusividade"
        verbose_name_plural = "Termos de exclusividade"
        ordering = ("-gerado_em", "-id")
        indexes = [models.Index(fields=("colaborador", "versao", "situacao"), name="rh_termo_situacao")]

    def __str__(self):
        return f"Termo {self.versao} · {self.colaborador} · {self.get_situacao_display()}"

    @property
    def assinado(self):
        return self.situacao == self.Estado.ASSINADO

    @property
    def aguardando(self):
        return self.situacao == self.Estado.ENVIADO

    def save(self, *args, **kwargs):
        if not self._state.adding:
            antes = TermoExclusividade.objects.filter(pk=self.pk).values_list("situacao", flat=True).first()
            if antes == self.Estado.ASSINADO:
                raise RegistroImutavel("Termo assinado não muda: se o texto mudar, gere a nova versão.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.situacao == self.Estado.ASSINADO:
            raise RegistroImutavel("Termo assinado não se apaga.")
        super().delete(*args, **kwargs)
