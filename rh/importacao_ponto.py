"""Importar o cartão de ponto do relógio: achar a ficha, preencher, lançar e comparar.

O PEDIDO (LEIA-ME-V10, seção 125): "adapte para enviar o arquivo pdf e
auto preencher os campos e informações do colaborador em questão no pdf.
para automatizar e agilizar o processo e monitoramento".

O CAMINHO, DE PONTA A PONTA:

  1. RECEBER (`receber`): o PDF passa pela conferência de sempre
     (`arquivos.conferir`: PDF de verdade, sem script, sem senha, até
     10 MB), é lido AQUI (`cartao_ponto.ler`, sem serviço de fora) e vai
     para o armazenamento privado (`ImportacaoPonto`). O mesmo arquivo
     (SHA-256) não entra duas vezes: volta "já recebido" com o que foi
     feito. Cada pessoa do arquivo vira um `CartaoPonto`, PENDENTE.
  2. ACHAR A FICHA (`casar_varios`): pelo CPF; sem CPF que bata, pelo PIS
     (quando o PIS do cartão é um PIS -- o relógio às vezes repete o CPF
     no lugar dele, e aí ele não conta). NUNCA pelo nome.
  3. CONFERIR A EMPRESA: o CNPJ do cartão tem de ser o da fábrica (o dos
     documentos e o da tela "Dados do contrato"). Diferente, o cartão não
     entra sem o "Importar mesmo assim".
  4. PREENCHER A FICHA (`plano_da_ficha` e `aplicar_na_ficha`): só o que
     está VAZIO entra sozinho (PIS, matrícula, a jornada dia a dia quando
     a da ficha é a mesma escrita de outro jeito). O que já está
     preenchido e é diferente vira DIVERGÊNCIA, com os dois valores em
     chips -- "manter o da ficha" (o padrão) ou "usar o do cartão" --, e só
     muda se alguém escolher. Nome, CPF e admissão nunca mudam calados.
  5. LANÇAR O PONTO (`importar`): cada hora do cartão vira uma
     `MarcacaoPonto` com a origem "rep" e a marca do relógio ((I), (P),
     (M), (C)), na mesma cadeia de NSR e hash do painel. A marcação é
     IMUTÁVEL (o modelo e o gatilho do banco): nada que já existe é
     editado ou apagado. Por isso:
       * a mesma hora que já está no ponto (±1 min) não entra de novo --
         reimportar o mesmo período (até de outro arquivo) não duplica;
       * dia que só tem marcações do relógio e ganhou uma a mais (o "(I)
         incluído" do relógio) recebe só a que faltava;
       * dia que tem marcação do PAINEL diferente do cartão NÃO é tocado:
         cada hora do cartão que falta vira um PEDIDO DE AJUSTE ("incluir
         marcação", pendente, com a justificativa dizendo de onde veio), e
         a Gestão decide na fila de sempre. A marcação do painel que o
         cartão não tem aparece como divergência (desconsiderar é
         decisão de gente, não da importação);
       * "Folga", "Feriado" (que não é nacional), "Férias", "Atestado" num
         dia que a jornada da ficha espera trabalho viram ABONO aprovado
         (a Gestão lança abono direto -- o mesmo poder), com a
         justificativa; "Falta" não precisa de nada: o espelho já conta
         falta no dia de jornada sem marcação.
       * dia antes da admissão, depois do desligamento ou no futuro não
         recebe marcação (aviso no resultado).
  6. GUARDAR O PDF NA PASTA: as páginas DA PESSOA (num arquivo com várias
     pessoas, só as dela) viram o documento "Cartão de ponto" da ficha,
     no armazenamento privado, aberto só pela view que confere quem pode.
  7. COMPARAR (`comparar`): o espelho do sistema no período do cartão,
     contra a linha TOTAIS e cada dia do cartão -- normais, noturno,
     faltas, falta e atraso, extras e banco --, com o PORQUÊ de cada
     diferença (a tolerância de 10 min que o relógio desconta e o espelho
     não -- Súmula 366 do TST --, a jornada da ficha diferente da do
     relógio, o dia com marcação do painel...).
"""

from __future__ import annotations

import io
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from core.email_utils import cnpj_empresa
from sistema_interno.utils import ErroDeFormulario
from sistema_interno.validacoes import cpf_valido, somente_digitos

from . import arquivos, cartao_ponto, ponto, servicos
from .arquivos import ArquivoConferido
from .models import (
    AjustePonto,
    CartaoPonto,
    Colaborador,
    DocumentoColaborador,
    ImportacaoPonto,
    MarcacaoPonto,
    OrigemMarcacao,
    RegistroRH,
    TipoDocumento,
    TipoMarcacao,
    erro_da_jornada_semana,
    normalizar_jornada_semana,
)
from .validadores import formatar_cpf, formatar_pis, pis_valido

#: Duas horas a até 1 minuto uma da outra são a mesma batida.
MESMA_BATIDA = 1

#: O que o relógio escreve no dia inteiro -> o motivo do abono.
MOTIVO_DO_ABONO = {
    "folga": AjustePonto.Motivo.FOLGA,
    "feriado": AjustePonto.Motivo.FERIADO,
    "ferias": AjustePonto.Motivo.FERIAS,
    "atestado": AjustePonto.Motivo.ATESTADO,
    "abono": AjustePonto.Motivo.OUTRO,
    "afastamento": AjustePonto.Motivo.OUTRO,
}

ROTULOS_DAS_OCORRENCIAS = {
    "folga": "Folga", "falta": "Falta", "feriado": "Feriado", "ferias": "Férias",
    "atestado": "Atestado", "abono": "Abono", "afastamento": "Afastamento",
}


def _sem_acento(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", str(texto or ""))
    return re.sub(r"\s+", " ", "".join(c for c in texto if not unicodedata.combining(c))).strip().upper()


def _hhmm(hora) -> str:
    return f"{hora:%H:%M}" if hora else ""


def nome_bonito(nome: str) -> str:
    """ "ANA PAULA DE SOUZA" -> "Ana Paula de Souza" (o relógio escreve tudo maiúsculo)."""
    pequenas = {"da", "de", "do", "das", "dos", "e"}
    partes = []
    for i, palavra in enumerate(re.sub(r"\s+", " ", nome or "").strip().lower().split(" ")):
        partes.append(palavra if (i and palavra in pequenas) else palavra[:1].upper() + palavra[1:])
    return " ".join(partes)


# ======================================================================
# A EMPRESA
# ======================================================================
def cnpjs_da_empresa() -> set:
    """O CNPJ dos documentos (settings) e o da tela "Dados do contrato" (uma consulta)."""
    cnpjs = {somente_digitos(cnpj_empresa())}
    try:
        from sistema_interno.models import DadosContrato

        gravado = DadosContrato.objects.order_by("id").values_list("cnpj", flat=True).first()
        if gravado:
            cnpjs.add(somente_digitos(gravado))
    except Exception:  # noqa: BLE001 -- sem a tabela, vale o dos documentos
        pass
    return {c for c in cnpjs if len(c) == 14}


def formatar_cnpj(cnpj: str) -> str:
    n = somente_digitos(cnpj)
    if len(n) != 14:
        return cnpj or "—"
    return f"{n[:2]}.{n[2:5]}.{n[5:8]}/{n[8:12]}-{n[12:]}"


# ======================================================================
# 1-2. RECEBER E ACHAR A FICHA
# ======================================================================
def pis_que_vale(pis: str, cpf: str) -> str:
    """O PIS do cartão, se for um PIS: o relógio às vezes repete o CPF no campo."""
    pis = somente_digitos(pis)
    if not pis or pis == somente_digitos(cpf) or not pis_valido(pis):
        return ""
    return pis


def casar_varios(cartoes) -> list:
    """[(colaborador ou None, "cpf"|"pis"|"")] na ordem dos cartões. Uma consulta só."""
    cpfs = {somente_digitos(c.cpf) for c in cartoes if cpf_valido(somente_digitos(c.cpf))}
    piss = {pis_que_vale(c.pis, c.cpf) for c in cartoes} - {""}
    if not (cpfs or piss):
        return [(None, "") for _ in cartoes]
    filtro = Q()
    if cpfs:
        filtro |= Q(cpf__in=cpfs)
    if piss:
        filtro |= Q(pis__in=piss)
    candidatos = list(Colaborador.objects.filter(filtro))
    por_cpf = {c.cpf: c for c in candidatos}
    por_pis = {c.pis: c for c in candidatos if c.pis}
    saida = []
    for c in cartoes:
        cpf = somente_digitos(c.cpf)
        if cpf in por_cpf:
            saida.append((por_cpf[cpf], "cpf"))
            continue
        pis = pis_que_vale(c.pis, c.cpf)
        if pis and pis in por_pis:
            saida.append((por_pis[pis], "pis"))
            continue
        saida.append((None, ""))
    return saida


def receber(conferido: ArquivoConferido, request) -> tuple:
    """(ImportacaoPonto, nova?). Lê, guarda no privado e cria um cartão por pessoa.

    Levanta `cartao_ponto.CartaoIlegivel` (com `titulo`) se não for um cartão.
    """
    existente = ImportacaoPonto.objects.filter(sha256=conferido.sha256).first()
    if existente is not None:
        return existente, False
    if conferido.formato != "pdf":
        raise cartao_ponto.CartaoIlegivel(
            "O cartão de ponto vem em PDF (o que o sistema do relógio exporta). Foto ou imagem não dá para ler.",
            titulo="Envie o PDF",
        )
    leitura = cartao_ponto.ler(conferido.dados)
    cnpjs = cnpjs_da_empresa()
    casamentos = casar_varios(leitura.cartoes)
    primeiro = leitura.cartoes[0]
    confere_tudo = all((not c.empresa_cnpj) or c.empresa_cnpj in cnpjs for c in leitura.cartoes)

    importacao = ImportacaoPonto(
        nome_original=conferido.nome_original,
        tamanho=conferido.tamanho,
        sha256=conferido.sha256,
        paginas=leitura.paginas,
        empresa_nome=primeiro.empresa_nome[:160],
        empresa_cnpj=primeiro.empresa_cnpj[:14],
        cnpj_confere=confere_tudo,
        avisos=leitura.avisos,
        enviado_por=request.user if getattr(request.user, "is_authenticated", False) else None,
    )
    importacao.arquivo.save("cartao.pdf", ContentFile(conferido.dados), save=False)
    try:
        with transaction.atomic():
            importacao.save()
            cartoes = []
            for ordem, (lido, (colaborador, por)) in enumerate(zip(leitura.cartoes, casamentos), start=1):
                dados = lido.para_json()
                dados["empresa"]["confere"] = (not lido.empresa_cnpj) or lido.empresa_cnpj in cnpjs
                dados["empresa"]["cnpjs_da_casa"] = sorted(cnpjs)
                cartoes.append(CartaoPonto(
                    importacao=importacao, ordem=ordem, colaborador=colaborador, casado_por=por,
                    nome=lido.nome[:150] or "Sem nome no cartão", cpf=lido.cpf[:11], pis=lido.pis[:11],
                    inicio=lido.inicio or (lido.dias[0].data if lido.dias else timezone.localdate()),
                    fim=lido.fim or (lido.dias[-1].data if lido.dias else timezone.localdate()),
                    dados=dados,
                ))
            CartaoPonto.objects.bulk_create(cartoes)
            servicos.registrar(
                request, RegistroRH.Acao.CARTAO_ENVIADO,
                colaborador=cartoes[0].colaborador if len(cartoes) == 1 else None,
                descricao=(
                    f"Cartão de ponto (PDF, {leitura.paginas} pág., {len(cartoes)} pessoa"
                    f"{'s' if len(cartoes) > 1 else ''}) · SHA-256 {conferido.sha256[:12]}…"
                ),
            )
    except Exception:
        importacao.arquivo.storage.delete(importacao.arquivo.name)
        raise
    return importacao, True


def recasar_pendentes(importacao) -> list:
    """Os cartões do arquivo; os pendentes sem ficha são procurados de novo (alguém cadastrou?)."""
    cartoes = list(importacao.cartoes.select_related("colaborador", "documento", "importado_por").order_by("ordem"))
    soltos = [c for c in cartoes if c.pendente and c.colaborador_id is None]
    if soltos:
        for cartao, (colaborador, por) in zip(soltos, casar_varios(soltos)):
            if colaborador is not None:
                cartao.colaborador = colaborador
                cartao.casado_por = por
                CartaoPonto.objects.filter(pk=cartao.pk).update(colaborador=colaborador, casado_por=por)
    return cartoes


# ======================================================================
# 4. A FICHA: O QUE O CARTÃO PREENCHE E O QUE DIVERGE
# ======================================================================
def semana_do_cartao(dados: dict) -> dict:
    """O "HORÁRIO DE TRABALHO" do cartão no formato de Colaborador.jornada_semana."""
    horario = dados.get("horario") or {}
    return normalizar_jornada_semana({dia: pares for dia, pares in horario.items() if pares})


def texto_da_semana(semana: dict) -> str:
    if not semana:
        return "—"
    provisorio = Colaborador(jornada_semana=semana)
    return " · ".join(f"{rotulo} {texto}" for rotulo, texto in provisorio.jornada_por_grupo)


def _semana_equivale(colaborador, semana: dict) -> bool:
    """A jornada simples da ficha é a mesma do cartão (escrita sem o horário do intervalo)?"""
    if colaborador.jornada_semana:
        return normalizar_jornada_semana(colaborador.jornada_semana) == semana
    if set(semana) != set(colaborador.jornada_dias or ""):
        return False
    provisorio = Colaborador(jornada_semana=semana)
    for chave in semana:
        dia = date(2024, 1, int(chave))  # 1/1/2024 é segunda
        pares = provisorio.pares_do_dia(dia)
        if not pares or pares[0][0] != colaborador.jornada_inicio or pares[-1][1] != colaborador.jornada_fim:
            return False
        if provisorio.minutos_previstos(dia) != colaborador.jornada_minutos:
            return False
    return True


def plano_da_ficha(colaborador, cartao: CartaoPonto) -> list[dict]:
    """O que o cartão faz na ficha. Cada linha: campo, rótulo, ficha, cartão, ação, nota.

    ação: "preencher" (vazio na ficha, entra sozinho), "igual", "divergente"
    (escolha com chips) ou "ignorado" (o valor do cartão não serve: a nota diz por quê).
    """
    dados = cartao.dados or {}
    func = dados.get("funcionario") or {}
    linhas = []

    nome_cartao = (func.get("nome") or "").strip()
    if nome_cartao and _sem_acento(nome_cartao) != _sem_acento(colaborador.nome):
        linhas.append({
            "campo": "nome", "rotulo": "Nome", "ficha": colaborador.nome, "cartao": nome_bonito(nome_cartao),
            "acao": "divergente",
            "nota": "O cartão foi casado pelo " + ("CPF" if cartao.casado_por == "cpf" else "PIS") + ", nunca pelo nome.",
        })

    cpf_cartao = somente_digitos(func.get("cpf"))
    if cartao.casado_por == "pis" and cpf_cartao and cpf_cartao != colaborador.cpf:
        linhas.append({
            "campo": "cpf", "rotulo": "CPF", "ficha": formatar_cpf(colaborador.cpf), "cartao": formatar_cpf(cpf_cartao),
            "acao": "divergente" if cpf_valido(cpf_cartao) else "ignorado",
            "nota": "Achado pelo PIS, com outro CPF no cartão: confira antes de importar."
            if cpf_valido(cpf_cartao) else "O CPF do cartão não confere pelos dígitos.",
        })

    pis_bruto = somente_digitos(func.get("pis"))
    pis = pis_que_vale(pis_bruto, cpf_cartao)
    if pis_bruto and not pis:
        if pis_bruto == cpf_cartao:
            nota = "O relógio repete o CPF no campo do PIS (o eSocial identifica pelo CPF): não é um PIS, não entra."
        else:
            nota = "O PIS do cartão não confere pelo dígito verificador: não entra."
        if not colaborador.pis:
            linhas.append({"campo": "pis", "rotulo": "PIS/NIS", "ficha": "—", "cartao": formatar_pis(pis_bruto),
                           "acao": "ignorado", "nota": nota})
    elif pis:
        if not colaborador.pis:
            outro = Colaborador.objects.filter(pis=pis).exclude(pk=colaborador.pk).values_list("nome", flat=True).first()
            linhas.append({
                "campo": "pis", "rotulo": "PIS/NIS", "ficha": "—", "cartao": formatar_pis(pis),
                "acao": "ignorado" if outro else "preencher",
                "nota": f"Esse PIS já está na ficha de {outro}." if outro else "",
                "valor": pis,
            })
        elif colaborador.pis != pis:
            linhas.append({"campo": "pis", "rotulo": "PIS/NIS", "ficha": colaborador.pis_formatado,
                           "cartao": formatar_pis(pis), "acao": "divergente", "nota": "", "valor": pis})

    admissao = func.get("admissao")
    if admissao:
        try:
            dia = date.fromisoformat(admissao)
        except ValueError:
            dia = None
        if dia and dia != colaborador.data_admissao:
            futuro = dia > timezone.localdate()
            linhas.append({
                "campo": "data_admissao", "rotulo": "Admissão",
                "ficha": f"{colaborador.data_admissao:%d/%m/%Y}" if colaborador.data_admissao else "—",
                "cartao": f"{dia:%d/%m/%Y}", "acao": "ignorado" if futuro else "divergente",
                "nota": "A data do cartão está no futuro." if futuro else (
                    "Dias antes da admissão da ficha não recebem marcação." if colaborador.data_admissao
                    and dia < colaborador.data_admissao else ""),
                "valor": dia.isoformat(),
            })

    matricula = (func.get("matricula") or "").strip()
    if matricula and matricula.strip("0"):
        if not colaborador.matricula:
            linhas.append({"campo": "matricula", "rotulo": "Matrícula", "ficha": "—", "cartao": matricula,
                           "acao": "preencher", "nota": "", "valor": matricula[:20]})
        elif colaborador.matricula != matricula:
            linhas.append({"campo": "matricula", "rotulo": "Matrícula", "ficha": colaborador.matricula,
                           "cartao": matricula, "acao": "divergente", "nota": "", "valor": matricula[:20]})

    semana = semana_do_cartao(dados)
    problema = erro_da_jornada_semana(semana) if semana else ""
    if semana and problema:
        linhas.append({
            "campo": "jornada_semana", "rotulo": "Jornada", "ficha": colaborador.jornada_texto,
            "cartao": texto_da_semana(semana), "acao": "ignorado",
            "nota": f"A jornada do relógio não fecha com a regra da ficha ({problema[:1].lower() + problema[1:]})",
        })
    elif semana:
        if _semana_equivale(colaborador, semana):
            if not colaborador.jornada_semana:
                linhas.append({
                    "campo": "jornada_semana", "rotulo": "Jornada dia a dia", "ficha": colaborador.jornada_texto,
                    "cartao": texto_da_semana(semana), "acao": "preencher",
                    "nota": "A mesma jornada da ficha, agora com o horário do intervalo de cada dia.",
                    "valor": semana,
                })
        else:
            linhas.append({
                "campo": "jornada_semana", "rotulo": "Jornada", "ficha": colaborador.jornada_texto,
                "cartao": texto_da_semana(semana), "acao": "divergente",
                "nota": "É por ela que o espelho conta atraso, falta e extra.", "valor": semana,
            })
    return linhas


def aplicar_na_ficha(colaborador, plano: list, escolhas: dict) -> tuple:
    """Preenche o vazio e aplica as divergências em que escolheram "usar o do cartão".

    Devolve (o que mudou [rótulos], o que ficou como estava [rótulos]).
    Levanta ErroDeFormulario se a ficha não fechar (ex.: PIS repetido).
    """
    mudou, manteve, campos = [], [], []
    for linha in plano:
        campo = linha["campo"]
        if linha["acao"] == "preencher" or (linha["acao"] == "divergente" and escolhas.get(campo) == "cartao"):
            if campo == "nome":
                colaborador.nome = linha["cartao"][:150]
            elif campo == "cpf":
                colaborador.cpf = somente_digitos(linha["cartao"])
            elif campo == "pis":
                colaborador.pis = linha["valor"]
            elif campo == "data_admissao":
                colaborador.data_admissao = date.fromisoformat(linha["valor"])
            elif campo == "matricula":
                colaborador.matricula = linha["valor"]
            elif campo == "jornada_semana":
                colaborador.jornada_semana = linha["valor"]
                campos += ["jornada_inicio", "jornada_fim", "jornada_intervalo_min", "jornada_dias"]
            else:
                continue
            campos.append(campo)
            mudou.append(linha["rotulo"])
        elif linha["acao"] == "divergente":
            manteve.append(linha["rotulo"])
    if not campos:
        return mudou, manteve
    try:
        colaborador.full_clean(exclude=["usuario", "colaborador_producao", "criado_por"], validate_unique=True)
    except ValidationError as erro:
        primeiro = next(iter(erro.message_dict.items())) if hasattr(erro, "message_dict") else ("", erro.messages)
        raise ErroDeFormulario(
            f"A ficha não fechou com o valor do cartão: {'; '.join(primeiro[1])}",
            titulo="Confira a escolha", campo=f"escolha_{primeiro[0]}" if primeiro[0] else "",
        ) from erro
    colaborador.save(update_fields=sorted(set(campos)) + ["atualizado_em"])
    return mudou, manteve


# ======================================================================
# 5. AS MARCAÇÕES
# ======================================================================
def _tipo_da_marca(marcas, indice) -> str:
    """O tipo pela coluna do cartão: ENT. 1 é a entrada; a última hora do dia, se nada falta depois, a saída."""
    marca = marcas[indice]
    numero = int(re.sub(r"\D", "", marca.coluna) or 1)
    if marca.coluna.startswith("ent"):
        return TipoMarcacao.ENTRADA if numero == 1 else TipoMarcacao.VOLTA_INTERVALO
    seguintes = marcas[indice + 1:]
    ultima = not any(s.hora for s in seguintes)
    falta_depois = any(s.palavra == "falta" for s in seguintes)
    return TipoMarcacao.SAIDA if ultima and not falta_depois else TipoMarcacao.SAIDA_INTERVALO


def _min(hora) -> int:
    return hora.hour * 60 + hora.minute


def _casar_horas(do_cartao: list, existentes: list) -> tuple:
    """(do cartão que não estão no ponto, do ponto que não estão no cartão)."""
    livres = list(existentes)
    novas = []
    for item in do_cartao:
        par = next((m for m in livres if abs(_min(m.hora_local) - _min(item["hora"])) <= MESMA_BATIDA), None)
        if par is None:
            novas.append(item)
        else:
            livres.remove(par)
    return novas, livres


def planejar(colaborador, cartao: CartaoPonto, *, hoje=None) -> dict:
    """O que a importação vai fazer, dia a dia, sem gravar nada (duas consultas)."""
    hoje = hoje or timezone.localdate()
    dados = cartao.dados or {}
    dias = cartao_ponto.dias_do_json(dados)
    existentes = defaultdict(list)
    for m in (MarcacaoPonto.objects.filter(colaborador=colaborador, data__range=(cartao.inicio, cartao.fim))
              .order_by("momento", "id")):
        existentes[m.data].append(m)
    ajustes = defaultdict(list)
    for a in AjustePonto.objects.filter(
        colaborador=colaborador, data__range=(cartao.inicio, cartao.fim),
        situacao__in=(AjustePonto.Estado.PENDENTE, AjustePonto.Estado.APROVADO),
    ):
        ajustes[a.data].append(a)
    feriados = {}
    for ano in range(cartao.inicio.year, cartao.fim.year + 1):
        feriados.update(ponto.feriados_nacionais(ano))

    plano = {"criar": [], "ajustes_incluir": [], "abonos": [], "ja_estavam": 0, "conflitos": [],
             "pulados": [], "dias_lidos": len(dias)}
    for dia in dias:
        d = dia.data
        horas = []
        for indice, marca in enumerate(dia.marcas):
            if marca.hora is not None:
                horas.append({"hora": marca.hora, "tipo": _tipo_da_marca(dia.marcas, indice),
                              "marcador": marca.marcador})
        if not horas and not dia.ocorrencia:
            continue
        if d > hoje:
            plano["pulados"].append({"data": d, "motivo": "dia que ainda não chegou"})
            continue
        if not colaborador.empregado_em(d):
            if horas:
                plano["pulados"].append({
                    "data": d, "motivo": "antes da admissão da ficha" if colaborador.data_admissao
                    and d < colaborador.data_admissao else "depois do desligamento",
                })
            continue
        if horas:
            no_ponto = existentes.get(d, [])
            if not no_ponto:
                plano["criar"].extend({"data": d, **h} for h in horas)
                continue
            novas, sobrando = _casar_horas(horas, no_ponto)
            plano["ja_estavam"] += len(horas) - len(novas)
            if not novas:
                continue
            so_do_relogio = all(m.origem == OrigemMarcacao.REP for m in no_ponto)
            if so_do_relogio and not sobrando:
                plano["criar"].extend({"data": d, **h} for h in novas)
                continue
            pedidos = []
            for h in novas:
                repetido = any(
                    a.tipo == AjustePonto.Tipo.INCLUIR and a.hora and _min(a.hora) == _min(h["hora"])
                    for a in ajustes.get(d, [])
                )
                if not repetido:
                    pedidos.append({"data": d, **h})
            plano["ajustes_incluir"].extend(pedidos)
            plano["conflitos"].append({
                "data": d,
                "cartao": [_hhmm(h["hora"]) for h in horas],
                "ponto": [f"{m.hora_local:%H:%M}" + ("" if m.origem else " (painel)") for m in no_ponto],
                "pedidos": len(pedidos),
            })
        elif dia.ocorrencia in MOTIVO_DO_ABONO:
            espera_trabalho = colaborador.trabalha_no_dia(d) and d not in feriados
            ja_tem = any(a.tipo == AjustePonto.Tipo.ABONO for a in ajustes.get(d, []))
            if espera_trabalho and not ja_tem and not existentes.get(d):
                plano["abonos"].append({"data": d, "ocorrencia": dia.ocorrencia})
    return plano


def _criar_marcacoes(colaborador, cartao, itens, usuario) -> int:
    """Grava as horas do cartão na cadeia do colaborador (NSR e hash seguidos), num INSERT só."""
    if not itens:
        return 0
    fuso = timezone.get_default_timezone()
    anterior = (
        MarcacaoPonto.objects.filter(colaborador=colaborador).order_by("-nsr").only("nsr", "hash").first()
    )
    nsr = anterior.nsr if anterior else 0
    hash_anterior = anterior.hash if anterior else ""
    novas = []
    for item in sorted(itens, key=lambda i: (i["data"], i["hora"])):
        nsr += 1
        marcacao = MarcacaoPonto(
            colaborador=colaborador,
            nsr=nsr,
            tipo=item["tipo"],
            momento=datetime.combine(item["data"], item["hora"], tzinfo=fuso),
            data=item["data"],
            ip=None,
            navegador=f"Cartão de ponto do relógio (REP-P) · arquivo #{cartao.importacao_id}"[:300],
            hash_anterior=hash_anterior,
            origem=OrigemMarcacao.REP,
            marcador=(item.get("marcador") or None),
            cartao=cartao,
        )
        marcacao.hash = marcacao.calcular_hash()
        hash_anterior = marcacao.hash
        novas.append(marcacao)
    MarcacaoPonto.objects.bulk_create(novas)
    return len(novas)


def _criar_ajustes(colaborador, cartao, plano, usuario) -> tuple:
    """Os pedidos de "incluir" (pendentes) e os abonos do cartão (aprovados pela Gestão que importa)."""
    agora = timezone.now()
    proprio = bool(colaborador.usuario_id and colaborador.usuario_id == getattr(usuario, "pk", None)
                   and not getattr(usuario, "is_superuser", False))
    quando = f"{timezone.localtime(agora):%d/%m/%Y}"
    novos = []
    for item in plano["ajustes_incluir"]:
        marca = f" ({item['marcador']})" if item.get("marcador") else ""
        ajuste = AjustePonto(
            colaborador=colaborador, tipo=AjustePonto.Tipo.INCLUIR, data=item["data"], hora=item["hora"],
            tipo_marcacao=item["tipo"], solicitado_por=usuario,
            justificativa=(
                f"Cartão de ponto do relógio (REP-P), importado em {quando}: "
                f"{TipoMarcacao(item['tipo']).label.lower()} às {item['hora']:%H:%M}{marca}, "
                "que não está no ponto do painel deste dia."
            ),
        )
        novos.append(ajuste)
    abonos = 0
    for item in plano["abonos"]:
        ocorrencia = ROTULOS_DAS_OCORRENCIAS.get(item["ocorrencia"], item["ocorrencia"])
        ajuste = AjustePonto(
            colaborador=colaborador, tipo=AjustePonto.Tipo.ABONO, data=item["data"],
            motivo_abono=MOTIVO_DO_ABONO[item["ocorrencia"]], solicitado_por=usuario,
            justificativa=(
                f"O cartão de ponto do relógio (REP-P) marca “{ocorrencia}” neste dia de jornada "
                f"(importado em {quando})."
            ),
        )
        if not proprio:
            ajuste.situacao = AjustePonto.Estado.APROVADO
            ajuste.decidido_por = usuario
            ajuste.decidido_em = agora
            ajuste.resposta = "Lançado pela importação do cartão de ponto do relógio."
        novos.append(ajuste)
        abonos += 1
    for ajuste in novos:
        ajuste.full_clean(exclude=["colaborador", "marcacao", "solicitado_por", "decidido_por"])
    if novos:
        AjustePonto.objects.bulk_create(novos)
    return len(plano["ajustes_incluir"]), abonos


def _pdf_da_pessoa(importacao, cartao) -> bytes:
    """As páginas do cartão desta pessoa (o arquivo inteiro, se ele é só dela)."""
    with importacao.arquivo.open("rb") as arquivo:
        dados = arquivo.read()
    paginas = (cartao.dados or {}).get("paginas") or []
    if not paginas or set(paginas) == set(range(1, (importacao.paginas or 0) + 1)):
        return dados
    from pypdf import PdfReader, PdfWriter

    leitor = PdfReader(io.BytesIO(dados), strict=False)
    escritor = PdfWriter()
    for numero in paginas:
        if 1 <= numero <= len(leitor.pages):
            escritor.add_page(leitor.pages[numero - 1])
    saida = io.BytesIO()
    escritor.write(saida)
    return saida.getvalue()


def _guardar_na_pasta(colaborador, cartao, usuario):
    dados = _pdf_da_pessoa(cartao.importacao, cartao)
    import hashlib

    sha = hashlib.sha256(dados).hexdigest()
    ja = DocumentoColaborador.objects.filter(colaborador=colaborador, sha256=sha).first()
    if ja is not None:
        return ja
    nome = f"cartao-de-ponto-{cartao.inicio:%Y-%m}.pdf"
    conferido = ArquivoConferido(
        formato="pdf", tipo_conteudo="application/pdf", extensao=".pdf", tamanho=len(dados),
        sha256=sha, nome_original=nome, dados=dados,
    )
    arquivos._conferir_pdf(dados)
    emitido = (cartao.dados or {}).get("emitido_em") or ""
    try:
        emissao = datetime.fromisoformat(emitido).date() if emitido else None
    except ValueError:
        emissao = None
    if emissao and emissao > timezone.localdate():
        emissao = None
    return servicos.guardar_documento(
        colaborador, conferido, tipo=TipoDocumento.CARTAO_PONTO,
        descricao=f"Cartão de ponto {cartao.periodo_texto}"[:120], emissao=emissao, usuario=usuario,
    )


def importar(cartao: CartaoPonto, request, *, escolhas=None, forcar_cnpj=False) -> dict:
    """Importa UM cartão (tudo-ou-nada). Devolve o resultado (também guardado no cartão)."""
    usuario = request.user
    with transaction.atomic():
        cartao = (
            CartaoPonto.objects.select_for_update().select_related("importacao").filter(pk=cartao.pk).first()
        )
        if cartao is None:
            raise ErroDeFormulario("Esse cartão não existe mais (o arquivo foi descartado).", titulo="Cartão não encontrado",
                                   status=404)
        if cartao.importado:
            raise ErroDeFormulario(
                f"Este cartão já foi importado em {timezone.localtime(cartao.importado_em):%d/%m/%Y às %H:%M}. "
                "Nada foi lançado de novo.", titulo="Já importado", status=409,
            )
        if cartao.situacao == CartaoPonto.Estado.DESCARTADO:
            raise ErroDeFormulario("Este cartão foi descartado.", titulo="Cartão descartado", status=409)
        if cartao.colaborador_id is None:
            raise ErroDeFormulario(
                "Nenhuma ficha tem o CPF (nem o PIS) deste cartão. Cadastre o colaborador com os dados do "
                "cartão e a importação segue sozinha.", titulo="Colaborador sem ficha",
                acao={"rotulo": "Cadastrar colaborador", "chave": "cadastrar"}, status=409,
            )
        empresa = (cartao.dados or {}).get("empresa") or {}
        if not empresa.get("confere", True) and not forcar_cnpj:
            raise ErroDeFormulario(
                f"O cartão é do CNPJ {formatar_cnpj(empresa.get('cnpj'))} ({empresa.get('nome') or 'sem nome'}), "
                f"e o da fábrica é {', '.join(formatar_cnpj(c) for c in empresa.get('cnpjs_da_casa') or []) or '—'}. "
                "Confira se o arquivo é mesmo daqui antes de lançar o ponto.",
                titulo="CNPJ de outra empresa", acao={"rotulo": "Importar mesmo assim", "chave": "forcar_cnpj"},
                status=409,
            )
        # A linha do colaborador travada: a cadeia (NSR e hash) não se bifurca
        # com alguém batendo o ponto pelo celular ao mesmo tempo.
        colaborador = Colaborador.objects.select_for_update().get(pk=cartao.colaborador_id)
        plano_ficha = plano_da_ficha(colaborador, cartao)
        mudou, manteve = aplicar_na_ficha(colaborador, plano_ficha, escolhas or {})
        plano = planejar(colaborador, cartao)
        criadas = _criar_marcacoes(colaborador, cartao, plano["criar"], usuario)
        pedidos, abonos = _criar_ajustes(colaborador, cartao, plano, usuario)
        documento = _guardar_na_pasta(colaborador, cartao, usuario)

        resultado = {
            "criadas": criadas,
            "ja_estavam": plano["ja_estavam"],
            "pedidos_de_ajuste": pedidos,
            "abonos": abonos,
            "conflitos": [{**c, "data": c["data"].isoformat()} for c in plano["conflitos"]],
            "pulados": [{**p, "data": p["data"].isoformat()} for p in plano["pulados"]],
            "preenchidos": mudou,
            "mantidos": manteve,
            "cnpj_forcado": bool(forcar_cnpj and not empresa.get("confere", True)),
        }
        cartao.situacao = CartaoPonto.Estado.IMPORTADO
        cartao.resultado = resultado
        cartao.documento = documento
        cartao.importado_por = usuario if getattr(usuario, "is_authenticated", False) else None
        cartao.importado_em = timezone.now()
        cartao.save(update_fields=["situacao", "resultado", "documento", "importado_por", "importado_em"])
        partes = [f"{criadas} marcaç{'ões' if criadas != 1 else 'ão'} nova{'s' if criadas != 1 else ''}"]
        if plano["ja_estavam"]:
            partes.append(f"{plano['ja_estavam']} já estavam")
        if pedidos:
            partes.append(f"{pedidos} pedido(s) de ajuste")
        if abonos:
            partes.append(f"{abonos} abono(s)")
        if mudou:
            partes.append("ficha: " + ", ".join(mudou))
        servicos.registrar(
            request, RegistroRH.Acao.CARTAO_IMPORTADO, colaborador=colaborador, documento=documento,
            descricao=f"Cartão de ponto {cartao.periodo_texto}: " + " · ".join(partes),
        )
    return resultado


def descartar(importacao, request):
    """Apaga o arquivo que ainda não foi importado (nada dele está no ponto)."""
    if importacao.cartoes.filter(situacao=CartaoPonto.Estado.IMPORTADO).exists():
        raise ErroDeFormulario(
            "Parte deste arquivo já foi importada: ele fica guardado como prova do que entrou no ponto.",
            titulo="Não dá para descartar", status=409,
        )
    nome = importacao.arquivo.name
    armazenamento = importacao.arquivo.storage
    servicos.registrar(
        request, RegistroRH.Acao.CARTAO_DESCARTADO,
        descricao=f"Cartão de ponto não importado (#{importacao.pk}, {importacao.paginas} pág.)",
    )
    importacao.delete()
    if nome:
        transaction.on_commit(lambda: armazenamento.delete(nome))


# ======================================================================
# 7. O CARTÃO CONTRA O SISTEMA
# ======================================================================
TOLERANCIA = ponto.TOLERANCIA_DIA

COMPARADOS = (
    ("normais", "Horas normais", "horas"),
    ("noturno", "Noturno (22h às 5h)", "horas"),
    ("dia_falta", "Dias de falta", "dias"),
    ("falta_atraso", "Falta e atraso", "horas"),
    ("extras", "Horas extras", "horas"),
    ("banco", "Banco de horas", "horas"),
)

MOTIVOS = {
    "tolerancia": (
        "Tolerância de 10 min",
        "O relógio desconta os 10 minutos de tolerância do dia; o espelho conta o dia inteiro quando passa "
        "deles (CLT, art. 58, § 1º, e Súmula 366 do TST). Diferença de regra, não de marcação.",
    ),
    "jornada": (
        "Jornada diferente",
        "A jornada da ficha neste dia não é a do relógio: ajuste a jornada da ficha (ou escolha \"usar a do "
        "cartão\" na importação).",
    ),
    "painel": (
        "Marcações do painel",
        "O dia tem marcação do painel diferente do cartão: as horas do cartão viraram pedidos de ajuste.",
    ),
    "pendente": (
        "Ajuste esperando decisão",
        "Há pedido de ajuste neste dia: só entra na conta depois de aprovado.",
    ),
    "feriado": (
        "Feriado",
        "Um dos dois conta feriado neste dia e o outro não.",
    ),
    "fora": (
        "Fora do contrato",
        "O dia está antes da admissão (ou depois do desligamento) da ficha.",
    ),
    "confira": (
        "Confira",
        "As marcações são as mesmas, mas a conta deu diferente: abra o dia no espelho.",
    ),
}


def _extras_do_cartao(totais: dict):
    if "extra_diurna" in totais or "extra_noturna" in totais:
        return totais.get("extra_diurna", 0) + totais.get("extra_noturna", 0)
    valores = [v for k, v in totais.items() if re.fullmatch(r"extra_\d+[dn]", k)]
    return sum(valores) if valores else None


def _banco_do_cartao(totais: dict):
    if "banco_saldo" in totais:
        return totais["banco_saldo"]
    if "banco_total" in totais:
        return totais["banco_total"]
    return None


def _do_cartao(totais: dict, chave: str):
    if chave == "extras":
        return _extras_do_cartao(totais)
    if chave == "banco":
        return _banco_do_cartao(totais)
    return totais.get(chave)


def _do_sistema(dia, chave):
    if chave == "normais":
        return dia.normais
    if chave == "noturno":
        return dia.noturno
    if chave == "dia_falta":
        return 1 if dia.falta else 0
    if chave == "falta_atraso":
        return dia.debito
    if chave == "extras":
        return dia.extra + dia.extra_100
    if chave == "banco":
        return dia.saldo
    return 0


def _motivo(dia_sistema, dia_cartao, chave, diferenca, conflitos):
    if dia_sistema.fora_do_contrato:
        return "fora"
    if dia_sistema.data in conflitos:
        return "painel"
    if dia_sistema.pendentes:
        return "pendente"
    previsto_cartao = sum(_min(b) - _min(a) for a, b in dia_cartao.previsto) if dia_cartao else 0
    esperado_ficha = sum(_min(b) - _min(a) for a, b in dia_sistema.previsto) if dia_sistema.previsto else 0
    if dia_cartao and dia_cartao.ocorrencia == "feriado" and not dia_sistema.feriado and not dia_sistema.abono:
        return "feriado"
    if dia_sistema.feriado and dia_cartao and dia_cartao.horas == [] and dia_cartao.ocorrencia not in ("feriado",):
        return "feriado"
    if dia_cartao and dia_cartao.previsto and previsto_cartao != dia_sistema.esperado and not dia_sistema.feriado \
            and not dia_sistema.abono and esperado_ficha != previsto_cartao:
        return "jornada"
    if chave in ("falta_atraso", "extras", "banco") and not dia_sistema.incompleto \
            and 0 < abs(diferenca) <= TOLERANCIA:
        return "tolerancia"
    return "confira"


def comparar(cartao: CartaoPonto, espelho=None) -> dict:
    """O cartão contra o espelho do sistema, no período do cartão.

    {"linhas": [{chave, rotulo, unidade, cartao, sistema, diferenca, confere}],
     "dias": [{data, itens: [{chave, rotulo, cartao, sistema, motivo}]}],
     "motivos": [{chave, titulo, texto, dias}], "confere": bool}
    """
    if cartao.colaborador_id is None:
        return {"linhas": [], "dias": [], "motivos": [], "confere": False, "sem_ficha": True}
    dados = cartao.dados or {}
    totais_cartao = dados.get("totais") or {}
    dias_cartao = {d.data: d for d in cartao_ponto.dias_do_json(dados)}
    if espelho is None:
        espelho = ponto.espelho_periodo(cartao.colaborador, cartao.inicio, cartao.fim, com_integridade=False)
    conflitos = set()
    for c in (cartao.resultado or {}).get("conflitos") or []:
        try:
            conflitos.add(date.fromisoformat(c["data"]))
        except (KeyError, ValueError):
            pass

    linhas = []
    por_dia = defaultdict(list)
    motivos = defaultdict(list)
    for chave, rotulo, unidade in COMPARADOS:
        do_cartao = _do_cartao(totais_cartao, chave)
        if do_cartao is None and chave in ("banco",):
            continue
        if do_cartao is None:
            soma = 0
            tem = False
            for d in dias_cartao.values():
                valor = _do_cartao(d.totais, chave)
                if valor is not None:
                    soma += valor
                    tem = True
            do_cartao = soma if tem else 0
        do_sistema = sum(_do_sistema(d, chave) for d in espelho.dias)
        diferenca = do_sistema - do_cartao
        linhas.append({
            "chave": chave, "rotulo": rotulo, "unidade": unidade,
            "cartao": do_cartao if unidade == "dias" else cartao_ponto.hm(do_cartao),
            "sistema": do_sistema if unidade == "dias" else cartao_ponto.hm(do_sistema),
            "diferenca": (f"{diferenca:+d}" if unidade == "dias" else
                          ("+" if diferenca > 0 else "") + cartao_ponto.hm(diferenca)) if diferenca else "",
            "diferenca_minutos": diferenca,
            "confere": diferenca == 0,
        })
        for dia in espelho.dias:
            lido = dias_cartao.get(dia.data)
            valor_cartao = (_do_cartao(lido.totais, chave) or 0) if lido else 0
            if chave == "banco" and _banco_do_cartao(totais_cartao) is None:
                continue
            valor_sistema = _do_sistema(dia, chave)
            if valor_sistema == valor_cartao:
                continue
            motivo = _motivo(dia, lido, chave, valor_sistema - valor_cartao, conflitos)
            por_dia[dia.data].append({
                "chave": chave, "rotulo": rotulo,
                "cartao": valor_cartao if unidade == "dias" else cartao_ponto.hm(valor_cartao),
                "sistema": valor_sistema if unidade == "dias" else cartao_ponto.hm(valor_sistema),
                "motivo": motivo,
            })
            if dia.data not in motivos[motivo]:
                motivos[motivo].append(dia.data)

    dias = [
        {"data": d, "itens": itens, "motivo": itens[0]["motivo"], "motivo_titulo": MOTIVOS[itens[0]["motivo"]][0]}
        for d, itens in sorted(por_dia.items())
    ]
    resumo = [
        {"chave": chave, "titulo": MOTIVOS[chave][0], "texto": MOTIVOS[chave][1], "dias": sorted(datas)}
        for chave, datas in sorted(motivos.items(), key=lambda item: -len(item[1]))
    ]
    return {
        "linhas": linhas, "dias": dias, "motivos": resumo,
        "confere": all(linha["confere"] for linha in linhas),
        "so_regra": bool(resumo) and all(m["chave"] == "tolerancia" for m in resumo),
    }


def soma_confere(cartao: CartaoPonto) -> bool:
    """A linha TOTAIS do cartão é a soma dos dias dele (a leitura não perdeu nada)?"""
    dados = cartao.dados or {}
    soma = Counter()
    for dia in dados.get("dias") or []:
        for chave, valor in (dia.get("totais") or {}).items():
            soma[chave] += valor
    return all(soma.get(chave, 0) == valor for chave, valor in (dados.get("totais") or {}).items())


def resumo_do_cartao(cartao: CartaoPonto) -> dict:
    """Os números do cartão para os cartõezinhos da tela."""
    dados = cartao.dados or {}
    dias = cartao_ponto.dias_do_json(dados)
    ocorrencias = Counter(d.ocorrencia for d in dias if d.ocorrencia)
    return {
        "dias": len(dias),
        "marcas": sum(len(d.horas) for d in dias),
        "faltas": ocorrencias.get("falta", 0),
        "folgas": ocorrencias.get("folga", 0),
        "feriados": ocorrencias.get("feriado", 0),
        "incompletos": sum(1 for d in dias if d.marcas_faltando),
        "marcadores": dict(Counter(m.marcador for d in dias for m in d.horas if m.marcador)),
        "totais": [
            {"rotulo": cartao_ponto.ROTULOS_DOS_TOTAIS.get(k, k),
             "valor": v if k == "dia_falta" else cartao_ponto.hm(v)}
            for k, v in (dados.get("totais") or {}).items()
        ],
        "soma_confere": soma_confere(cartao),
        "avisos": dados.get("avisos") or [],
        "alteracoes": dados.get("alteracoes") or [],
    }
