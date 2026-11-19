"""O essencial, o repetido e a criação: o documento vira O.S. sozinho.

O ESSENCIAL PARA A O.S. NASCER SEM NINGUÉM CONFERIR -- e nada além disso:

  1. QUEM: o cliente ligado a um cadastro pelo CPF/CNPJ, e-mail ou
     telefone; ou, sem cadastro, nome e um contato (telefone ou e-mail)
     para cadastrar pelas regras da aba Clientes. Só o nome NÃO basta: ele
     bate com outro cadastro ou não dá para falar com a pessoa -- a folha
     pergunta.
  2. O QUÊ: o equipamento (é o único campo que a O.S. exige à mão), e o
     que o cliente pediu ou o que foi feito (defeito, diagnóstico, serviço
     executado ou ao menos uma linha de peça ou serviço).
  3. AS CONTAS, quando há dinheiro: cada linha com quantidade e valor, e a
     soma (itens + frete − desconto) igual ao total escrito no documento.
     Um centavo de diferença não passa: é a regra do orçamento.
  4. CONCLUÍDA, SÓ COM O SERVIÇO EXECUTADO escrito -- a mesma regra da
     criação à mão ("é o que o cliente lê para saber pelo que está pagando").

O resto o documento traz quando traz (técnico, datas, garantia, prioridade,
série, observações), e o que não entra vira AVISO na linha do documento
(técnico que não é da equipe, data marcada que já passou, garantia vencida),
nunca motivo para segurar a O.S.

AS MESMAS REGRAS DA CRIAÇÃO À MÃO (views_ordens_servico.acao_save): a
situação nunca nasce Rascunho (a da tela nova é "Aguardando ciência") nem
Substituída; agenda no passado não vale para o serviço por fazer; garantia
vencida não entra; Concluída ganha a data de conclusão; a identificação
sem etiqueta vira "LS-PAT-000123"; o responsável é quem importou; até 80
linhas. O pagamento escrito no papel só é lançado para quem pode lançar
pagamento (Financeiro e Gestão) -- para os outros, vira aviso.

O REPETIDO: o mesmo arquivo (SHA-256, único no banco), o mesmo texto salvo
de novo, o número que o próprio painel imprime ("OS-00042/2026") e o número
de O.S. escrito no papel com o mesmo cliente. Repetido não cria nada: a
resposta é "já importada", com o caminho para a O.S.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation

from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction
from django.db.models import Exists, OuterRef, Q
from django.urls import reverse
from django.utils import timezone

from ..importacao_word import catalogo as cat
from ..importacao_word import deterministica as det
from ..permissoes import capacidades
from ..utils import ErroDeFormulario
from . import arquivo as arq
from . import campos
from . import cliente as cli
from . import contexto

logger = logging.getLogger(__name__)

VERSAO = 1
CENTAVO = Decimal("0.01")
LIMITE_DINHEIRO = Decimal("9999999999.99")
MAXIMO_DE_ITENS = 80
HORA_DA_AGENDA = time(9, 0)
HORA_DO_REGISTRO = time(12, 0)

POR_FAZER = ("rascunho", "aguardando_resposta", "aberta", "agendada")
#: Linhas de serviço que não descrevem o serviço (não viram "serviço executado").
SERVICO_SEM_DESCRICAO = {
    "mao de obra", "servico", "servicos", "hora tecnica", "horas tecnicas", "visita tecnica", "taxa de servico",
    "conserto", "reparo", "manutencao", "servico prestado", "servicos prestados",
}


# ======================================================================
# UTILIDADES DE TEXTO E DINHEIRO
# ======================================================================
def _dinheiro(valor) -> Decimal | None:
    if valor in (None, ""):
        return None
    try:
        return Decimal(str(valor)).quantize(CENTAVO)
    except (InvalidOperation, ValueError):
        return None


def _texto_dinheiro(valor) -> str:
    return "" if valor is None else str(Decimal(valor).quantize(CENTAVO))


def brl(valor) -> str:
    return f"R$ {det.moeda(valor)}" if valor is not None else ""


def _data_br(iso: str) -> str:
    if not iso:
        return ""
    try:
        if "T" in iso:
            momento = timezone.localtime(datetime.fromisoformat(iso))
            return momento.strftime("%d/%m/%Y %H:%M")
        return date.fromisoformat(iso).strftime("%d/%m/%Y")
    except ValueError:
        return ""


def _momento(lido: dict | None, hora_padrao: time) -> datetime | None:
    if not lido or not lido.get("data"):
        return None
    dia = date.fromisoformat(lido["data"])
    hora = hora_padrao
    if lido.get("hora"):
        horas, minutos = (int(p) for p in lido["hora"].split(":"))
        hora = time(horas, minutos)
    try:
        return timezone.make_aware(datetime.combine(dia, hora), timezone.get_current_timezone())
    except (OverflowError, ValueError):
        return None


# ======================================================================
# A LEITURA
# ======================================================================
def montar(nome: str, lido: dict, *, hoje: date, ctx: dict) -> dict:
    """O documento lido, no formato que mora em `DocumentoOrdemServico.leitura`."""
    linhas = campos.separar_linhas(lido["linhas"])
    linhas, tipos = campos.preparar_tabelas(linhas)
    os_lido = campos.ler(linhas)
    consumidas = os_lido["consumidas"]
    extras = {extra["id"][:-2]: extra for extra in os_lido["linhas_extra"]}
    linhas_cliente = []
    for linha in linhas:
        if linha["id"] in consumidas:
            if linha["id"] in extras:
                linhas_cliente.append(extras[linha["id"]])
            continue
        linhas_cliente.append(linha)
    leitura_cliente = cli.ler(linhas_cliente, hoje=hoje, contexto=ctx)
    dados = leitura_cliente["dados"]
    lido_det = leitura_cliente["lido"]
    v = os_lido["valores"]
    avisos: list[str] = []
    if dados.get("documento_invalido"):
        avisos.append(f"O CPF/CNPJ do documento ({dados['documento_invalido']}) não confere nos dígitos: não entrou.")

    # ------------------------------------------------------------ itens
    das_tabelas = campos.itens_das_tabelas(lido_det["itens"], linhas, tipos=tipos, secoes=os_lido["secoes_tabela"])
    dos_paragrafos = campos.itens_dos_paragrafos(lido_det["itens"], consumidas)
    itens = campos.juntar_itens(das_tabelas, os_lido["itens_rotulo"], dos_paragrafos)
    precisa_catalogo = any(item["tipo"] == "peca" for item in itens) or not v.get("equipamento")
    catalogo = contexto.catalogo() if precisa_catalogo else []
    pecas = [p for p in catalogo if p["id"].startswith("r:")]
    itens_json = []
    for item in itens:
        peca_id = None
        unitario = item["valor_unitario"]
        preco_catalogo = False
        if item["tipo"] == "peca" and pecas:
            casado = cat.casar_item(item["descricao"], pecas, quantos=1)
            if casado["escolhido"] and casado["confianca"] == "alta":
                peca_id = int(casado["escolhido"][2:])
                if unitario is None and not item["recusa"]:
                    produto = next((p for p in pecas if p["id"] == casado["escolhido"]), None)
                    if produto and produto.get("preco") is not None:
                        unitario = Decimal(produto["preco"]).quantize(CENTAVO)
                        preco_catalogo = True
        itens_json.append({
            "tipo": item["tipo"], "descricao": item["descricao"],
            "quantidade": int(item["quantidade"]) if item["quantidade"] else None,
            "valor_unitario": _texto_dinheiro(unitario) if unitario is not None else None,
            "peca_id": peca_id, "preco_catalogo": preco_catalogo,
            "recusa": item["recusa"], "fonte": item["fonte"], "como": item["como"],
        })
        if preco_catalogo:
            avisos.append(f"“{item['descricao']}” sem valor no documento: entrou o preço do catálogo, "
                          f"{brl(unitario)}.")

    # -------------------------------------------------------- equipamento
    equipamento = v.get("equipamento", "")
    equipamento_como = "documento" if equipamento else ""
    if not equipamento and catalogo:
        empresa = ctx["empresa"]
        fora = {l["id"] for l in linhas if det.linha_da_empresa(l["texto"], empresa)}
        citados = cat.brinquedos_citados(linhas, catalogo, fora=fora)
        citado = next((c for c in citados if c.get("produto_citado")), None)
        if citado:
            equipamento = citado["descricao"]["valor"]
            equipamento_como = "catalogo"

    # ------------------------------------------------------------ valores
    cd = lido_det["campos"]

    def valor_det(nome_campo):
        return (cd.get(nome_campo) or {}).get("valor")

    frete = valor_det("frete")
    desconto = valor_det("desconto")
    percentual = valor_det("desconto_percentual")
    if desconto is None and percentual is not None:
        desconto = campos.desconto_percentual(itens, percentual)
        if desconto is not None:
            avisos.append(f"Desconto de {det.moeda(percentual).rstrip('0').rstrip(',')}% sobre os itens: "
                          f"{brl(desconto)}.")
    total_documento = valor_det("valor_final") or valor_det("total")
    for nome_campo in ("total", "frete", "desconto", "subtotal"):
        if (cd.get(nome_campo) or {}).get("conflitos"):
            avisos.append("O documento traz dois valores diferentes para o "
                          f"{'total' if nome_campo == 'total' else nome_campo}: confira na O.S.")
    forma_pagamento = valor_det("forma_pagamento") or ""
    if forma_pagamento:
        forma_pagamento = det.normalizar_pagamento(forma_pagamento)[:120]

    # ---------------------------------------------------- situação e datas
    servico_executado = v.get("servico_executado", "")
    agenda = _momento(v.get("agendada_para"), HORA_DA_AGENDA)
    if agenda and v.get("hora") and not (v.get("agendada_para") or {}).get("hora"):
        horas, minutos = (int(p) for p in v["hora"].split(":"))
        agenda = agenda.replace(hour=horas, minute=minutos)
    agora = timezone.now()
    status = v.get("status") or ""
    status_como = "documento" if status else ""
    if not status:
        if servico_executado:
            status, status_como = "concluida", "serviço executado escrito"
        elif agenda and agenda > agora:
            status, status_como = "agendada", "data marcada"
        else:
            status, status_como = "aguardando_resposta", "padrão da O.S. nova"
    if status == "concluida" and not servico_executado:
        # "Troca da lona" diz o que foi feito; "Mão de obra" não diz nada ao
        # cliente -- sem linha que descreva o serviço, a folha pergunta.
        servicos = [i["descricao"] for i in itens_json
                    if i["tipo"] == "servico" and campos.chave(i["descricao"]) not in SERVICO_SEM_DESCRICAO]
        if servicos:
            servico_executado = "; ".join(servicos)[:2000]
            avisos.append("Serviço executado montado com as linhas de serviço do documento.")
    if agenda and agenda < agora and status in POR_FAZER:
        avisos.append(
            f"A data marcada no documento ({timezone.localtime(agenda):%d/%m/%Y %H:%M}) já passou e o serviço "
            "não consta como feito: a O.S. ficou sem agenda. Marque a nova data na O.S."
        )
        agenda = None
        if status == "agendada":
            status, status_como = "aberta", "a data marcada já passou"
    data_documento = None
    if v.get("data_documento"):
        data_documento = date.fromisoformat(v["data_documento"]["data"])
    elif lido_det.get("data_documento"):
        data_documento = lido_det["data_documento"]
    iniciada = _momento(v.get("iniciada_em"), HORA_DO_REGISTRO)
    concluida = _momento(v.get("concluida_em"), HORA_DO_REGISTRO)
    if status == "concluida" and concluida is None:
        if agenda and agenda <= agora:
            concluida = agenda
        elif data_documento:
            concluida = _momento({"data": data_documento.isoformat()}, HORA_DO_REGISTRO)
    if status != "concluida":
        concluida = None
    if status not in ("em_execucao", "aguardando_peca", "concluida", "cancelada"):
        iniciada = None
    if concluida and concluida > agora + timedelta(days=1):
        concluida = None
    garantia_lida = v.get("garantia") or os_lido.get("garantia_em_frase")
    base_garantia = (timezone.localtime(concluida).date() if concluida else None) or data_documento \
        or timezone.localdate()
    garantia = campos.garantia_ate(garantia_lida, base_garantia)
    if garantia and garantia < timezone.localdate():
        avisos.append(f"A garantia escrita no documento terminou em {garantia:%d/%m/%Y}: não entrou na O.S.")
        garantia = None

    # ----------------------------------------------------------- técnico
    tecnico = None
    tecnico_nome = cli.nome_de_tecnico(v.get("tecnico", ""))
    if tecnico_nome:
        tecnico = cli.casar_tecnico(tecnico_nome, ctx["tecnicos"])
        if tecnico is None:
            avisos.append(f"Técnico “{tecnico_nome}” não está na equipe do painel: escolha o técnico na O.S.")

    numero = (v.get("numero_os") or "")[:40]
    leitura = {
        "versao": VERSAO,
        "arquivo": nome,
        "formato": lido["formato"],
        "os": {
            "equipamento": equipamento[:180], "equipamento_como": equipamento_como,
            "numero_serie": v.get("numero_serie", "")[:80],
            "defeito_relatado": v.get("defeito_relatado", ""),
            "diagnostico": v.get("diagnostico", ""),
            "servico_executado": servico_executado,
            "observacoes": v.get("observacoes", ""),
            "tipo": v.get("tipo") or os_lido["tipo_pelo_titulo"] or "manutencao",
            "status": status, "status_como": status_como,
            "prioridade": v.get("prioridade") or os_lido["prioridade_solta"] or "normal",
            "tecnico_id": tecnico["id"] if tecnico else None,
            "tecnico_nome": tecnico["nome"] if tecnico else tecnico_nome,
            "agendada_para": agenda.isoformat() if agenda else "",
            "iniciada_em": iniciada.isoformat() if iniciada else "",
            "concluida_em": concluida.isoformat() if concluida else "",
            "garantia_ate": garantia.isoformat() if garantia else "",
            "data_documento": data_documento.isoformat() if data_documento else "",
            "endereco_servico": (v.get("endereco_servico") or dados.get("endereco_texto", ""))[:320],
            "forma_pagamento": forma_pagamento,
            "frete": _texto_dinheiro(frete) if frete is not None else "",
            "desconto": _texto_dinheiro(desconto) if desconto is not None else "",
            "total_documento": _texto_dinheiro(total_documento) if total_documento is not None else "",
            "subtotal_documento": _texto_dinheiro(valor_det("subtotal")) if valor_det("subtotal") is not None else "",
            "valor_pago": _texto_dinheiro(v["valor_pago"]) if v.get("valor_pago") is not None else "",
            "status_pagamento": v.get("status_pagamento", ""),
            "chamado": os_lido.get("chamado"),
            "numero": numero,
            "numero_do_painel": list(os_lido["numero_do_painel"]) if os_lido.get("numero_do_painel") else None,
        },
        "itens": itens_json,
        "cliente": dados,
        "fontes": os_lido["fontes"],
        "avisos": avisos,
    }
    return leitura


# ======================================================================
# O ESSENCIAL
# ======================================================================
def contas(leitura: dict) -> dict:
    os_ = leitura["os"]
    soma = Decimal("0.00")
    completos = True
    for item in leitura["itens"]:
        unitario = _dinheiro(item.get("valor_unitario"))
        if unitario is None or not item.get("quantidade") or item.get("recusa"):
            completos = False
            continue
        soma += (unitario * int(item["quantidade"])).quantize(CENTAVO)
    frete = _dinheiro(os_.get("frete")) or Decimal("0.00")
    desconto = _dinheiro(os_.get("desconto")) or Decimal("0.00")
    total = max(soma + frete - desconto, Decimal("0.00"))
    return {"itens": soma, "frete": frete, "desconto": desconto, "total": total, "completos": completos}


def pendencias(leitura: dict) -> list[dict]:
    """O que falta para a O.S. nascer. Vazia: cria."""
    os_ = leitura["os"]
    faltas = []
    vinculo = leitura["cliente"].get("vinculo") or {}
    if vinculo.get("modo") not in ("existente", "novo", "sem_cadastro"):
        faltas.append({"campo": "cliente", "rotulo": "Cliente",
                       "motivo": vinculo.get("motivo") or "quem é o cliente desta O.S.?"})
    if not os_.get("equipamento"):
        faltas.append({"campo": "equipamento", "rotulo": "Equipamento",
                       "motivo": "o documento não diz em que equipamento é o serviço"})
    if not (os_.get("defeito_relatado") or os_.get("diagnostico") or os_.get("servico_executado")
            or leitura["itens"]):
        faltas.append({"campo": "defeito_relatado", "rotulo": "O que o cliente pediu",
                       "motivo": "o documento não diz o defeito, o pedido ou o que foi feito"})
    if os_.get("status") == "concluida" and not os_.get("servico_executado"):
        faltas.append({"campo": "servico_executado", "rotulo": "Serviço executado",
                       "motivo": "a O.S. está concluída e o documento não diz o que foi feito"})
    conta = contas(leitura)
    total_documento = _dinheiro(os_.get("total_documento"))
    subtotal_documento = _dinheiro(os_.get("subtotal_documento"))
    motivo_valores = ""
    if not conta["completos"]:
        sem_valor = [i["descricao"] for i in leitura["itens"]
                     if _dinheiro(i.get("valor_unitario")) is None or not i.get("quantidade") or i.get("recusa")]
        motivo_valores = "sem quantidade ou valor: " + ", ".join(f"“{d[:40]}”" for d in sem_valor[:3])
    elif total_documento is not None and not leitura["itens"]:
        motivo_valores = f"o documento diz {brl(total_documento)}, mas não diz de quê"
    elif total_documento is not None and conta["total"] != total_documento:
        motivo_valores = (f"as linhas dão {brl(conta['total'])} e o documento diz {brl(total_documento)}")
    elif subtotal_documento is not None and conta["itens"] != subtotal_documento:
        motivo_valores = (f"as linhas somam {brl(conta['itens'])} e o subtotal do documento é "
                          f"{brl(subtotal_documento)}")
    if motivo_valores:
        faltas.append({"campo": "valores", "rotulo": "Valores", "motivo": motivo_valores})
    return faltas


def resolver_cliente(leitura: dict) -> object | None:
    """Liga ao cadastro (ou decide cadastrar). Devolve o Cliente achado, se houver."""
    dados = leitura["cliente"]
    escolha = dados.get("escolha") or {}
    if escolha.get("modo") == "sem_cadastro" and dados.get("nome"):
        dados["vinculo"] = {"modo": "sem_cadastro", "motivo": "só o nome na O.S., sem cadastro"}
        return None
    if escolha.get("modo") == "existente" and escolha.get("cliente_id"):
        existente = _cliente_por_id(escolha["cliente_id"])
        if existente is not None:
            dados["vinculo"] = {"modo": "existente", "cliente_id": existente.pk,
                                "motivo": "escolhido na folha", "nome": existente.nome_cliente}
            return existente
    casamento = cli.casar(dados)
    if casamento["modo"] == "existente":
        existente = casamento["cliente"]
        dados["vinculo"] = {"modo": "existente", "cliente_id": existente.pk, "motivo": casamento["motivo"],
                            "nome": existente.nome_cliente}
        return existente
    if casamento["modo"] in ("duvida", "conflito") and escolha.get("modo") != "novo":
        dados["vinculo"] = {"modo": casamento["modo"], "motivo": casamento["motivo"],
                            "candidatos": casamento["candidatos"]}
        return None
    motivo = cli.pode_cadastrar(dados)
    if motivo:
        dados["vinculo"] = {"modo": "falta", "motivo": motivo, "candidatos": casamento.get("candidatos", [])}
        return None
    dados["vinculo"] = {"modo": "novo", "motivo": "será cadastrado pelas regras da aba Clientes"}
    return None


def _cliente_por_id(pk):
    from ..models import Cliente, EnderecoCliente

    try:
        pk = int(pk)
    except (TypeError, ValueError):
        return None
    return (Cliente.objects.filter(pk=pk)
            .annotate(tem_endereco=Exists(EnderecoCliente.objects.filter(cliente=OuterRef("pk")))).first())


# ======================================================================
# O REPETIDO
# ======================================================================
def procurar_repetido(lido: dict, numero: str, numero_do_painel):
    """(o documento já guardado, como) -- ou (None, "").

    Uma consulta para o arquivo, o texto e o número escrito; outra só quando
    o documento traz o número que o próprio painel imprime.
    """
    from ..models import DocumentoOrdemServico, OrdemServico

    filtro = Q(sha256=lido["sha256"])
    if lido.get("texto_sha256"):
        filtro |= Q(texto_sha256=lido["texto_sha256"])
    if numero:
        filtro |= Q(numero_no_documento=numero, situacao=DocumentoOrdemServico.Situacao.CRIADA)
    candidatos = list(DocumentoOrdemServico.objects.filter(filtro).select_related("ordem", "ordem__cliente")[:10])
    for documento in candidatos:
        if documento.sha256 == lido["sha256"]:
            return documento, "o mesmo arquivo"
    for documento in candidatos:
        if lido.get("texto_sha256") and documento.texto_sha256 == lido["texto_sha256"]:
            return documento, "o mesmo texto"
    if numero_do_painel:
        pk, ano = numero_do_painel
        ordem = OrdemServico.objects.filter(pk=pk, criacao__year=ano).first()
        if ordem is not None:
            return ordem, "o número da O.S. deste painel"
    return [d for d in candidatos if numero and d.numero_no_documento == numero and d.ordem_id], "numero"


def _mesmo_cliente_do_numero(candidatos, leitura, existente) -> object | None:
    """O número escrito no papel só repete com o mesmo cliente (ou o mesmo equipamento)."""
    nome = cat._nome_para_comparar(leitura["cliente"].get("nome", ""))  # noqa: SLF001
    equipamento = cat._normalizar(leitura["os"].get("equipamento", ""))  # noqa: SLF001
    for documento in candidatos:
        ordem = documento.ordem
        if existente is not None and ordem.cliente_id == existente.pk:
            return documento
        if nome and cat._nome_para_comparar(ordem.nome_cliente) == nome:  # noqa: SLF001
            return documento
        if not nome and existente is None and equipamento and cat._normalizar(ordem.equipamento) == equipamento:  # noqa: SLF001
            return documento
    return None


# ======================================================================
# A CRIAÇÃO
# ======================================================================
def _criar_ordem(request, leitura: dict, existente, *, documento=None, conteudo: bytes | None = None,
                 lido: dict | None = None):
    """Cria cliente (quando é o caso), O.S., itens e o documento anexado. Tudo ou nada."""
    from core.models import Manutencao

    from ..models import DocumentoOrdemServico, ItemOrdemServico, OrdemServico

    os_ = leitura["os"]
    dados = leitura["cliente"]
    vinculo = dados.get("vinculo") or {}
    usuario = request.user
    completados = []
    cliente = None
    cliente_novo = False
    if vinculo.get("modo") in ("existente", "novo"):
        gravado = cli.gravar(request, dados, existente if vinculo["modo"] == "existente" else None,
                             arquivo=leitura["arquivo"])
        cliente = gravado["cliente"]
        cliente_novo = gravado["novo"]
        completados = gravado["completados"]

    ordem = OrdemServico(
        cliente=cliente,
        nome_cliente=(cliente.nome_cliente if cliente else dados.get("nome", ""))[:120],
        contato=dados.get("contato", "")[:120],
        whatsapp_cliente=(dados.get("telefone", "") if dados.get("whatsapp") else "")[:24],
        email_cliente=dados.get("email", "")[:254],
        endereco_servico=os_.get("endereco_servico", "")[:320],
        tipo=os_["tipo"] if os_["tipo"] in OrdemServico.Tipo.values else OrdemServico.Tipo.MANUTENCAO,
        status=os_["status"],
        prioridade=os_["prioridade"] if os_["prioridade"] in OrdemServico.Prioridade.values
        else OrdemServico.Prioridade.NORMAL,
        equipamento=os_["equipamento"][:180],
        numero_serie=os_.get("numero_serie", "")[:80],
        defeito_relatado=os_.get("defeito_relatado", ""),
        diagnostico=os_.get("diagnostico", ""),
        servico_executado=os_.get("servico_executado", ""),
        observacoes=os_.get("observacoes", ""),
        forma_pagamento=os_.get("forma_pagamento", "")[:120],
        frete=min(_dinheiro(os_.get("frete")) or Decimal("0.00"), LIMITE_DINHEIRO),
        desconto=min(_dinheiro(os_.get("desconto")) or Decimal("0.00"), LIMITE_DINHEIRO),
        agendada_para=datetime.fromisoformat(os_["agendada_para"]) if os_.get("agendada_para") else None,
        iniciada_em=datetime.fromisoformat(os_["iniciada_em"]) if os_.get("iniciada_em") else None,
        concluida_em=datetime.fromisoformat(os_["concluida_em"]) if os_.get("concluida_em") else None,
        garantia_ate=date.fromisoformat(os_["garantia_ate"]) if os_.get("garantia_ate") else None,
        tecnico_id=os_.get("tecnico_id"),
        responsavel=usuario,
    )
    if ordem.status in (OrdemServico.Status.RASCUNHO, OrdemServico.Status.SUBSTITUIDA) \
            or ordem.status not in OrdemServico.Status.values:
        ordem.status = OrdemServico.Status.AGUARDANDO_RESPOSTA
    if ordem.status == OrdemServico.Status.EM_EXECUCAO and not ordem.iniciada_em:
        ordem.iniciada_em = timezone.now()
    if ordem.status == OrdemServico.Status.CONCLUIDA and not ordem.concluida_em:
        ordem.concluida_em = timezone.now()
    if os_.get("chamado"):
        ordem.manutencao = Manutencao.objects.filter(pk=os_["chamado"]).first()
    ordem.save()
    if not ordem.numero_serie:
        # A mesma identificação interna da criação à mão.
        ordem.numero_serie = f"LS-PAT-{ordem.pk:06d}"
        ordem.save(update_fields=["numero_serie", "atualizado"])

    itens = []
    for item in leitura["itens"][:MAXIMO_DE_ITENS]:
        tipo = item["tipo"] if item["tipo"] in ItemOrdemServico.Tipo.values else ItemOrdemServico.Tipo.OUTRO
        descricao = (item.get("descricao") or "").strip() or ItemOrdemServico.Tipo(tipo).label
        itens.append(ItemOrdemServico(
            ordem=ordem, tipo=tipo, descricao=descricao[:200],
            peca_id=item.get("peca_id") if tipo == ItemOrdemServico.Tipo.PECA else None,
            quantidade=max(1, min(int(item.get("quantidade") or 1), 99999999)),
            valor_unitario=min(_dinheiro(item.get("valor_unitario")) or Decimal("0.00"), LIMITE_DINHEIRO),
        ))
    if itens:
        ItemOrdemServico.objects.bulk_create(itens)
    ordem._prefetched_objects_cache = {"itens": itens}

    avisos = list(leitura.get("avisos") or [])
    pago = _dinheiro(os_.get("valor_pago"))
    situacao_pagamento = os_.get("status_pagamento", "")
    if pago is not None or situacao_pagamento in ("pago", "parcial"):
        if capacidades(usuario).get("ordens_servico_pagamento"):
            valor = pago if pago is not None else (ordem.total if situacao_pagamento == "pago" else None)
            if valor is not None:
                ordem.registrar_pagamento(valor, f"Lido do documento “{leitura['arquivo'][:80]}”.")
        else:
            escrito = brl(pago) if pago is not None else "pago"
            avisos.append(f"O documento diz pagamento ({escrito}): quem lança é o Financeiro ou a Gestão.")
    if completados:
        avisos.append("Cadastro do cliente completado com: " + ", ".join(completados) + ".")

    leitura = dict(leitura, avisos=avisos)
    novo = documento is None
    if novo:
        documento = DocumentoOrdemServico(
            formato=lido["formato"], nome_arquivo=leitura["arquivo"][:150], tamanho_arquivo=len(conteudo),
            sha256=lido["sha256"], texto_sha256=lido.get("texto_sha256", ""),
            numero_no_documento=os_.get("numero", "")[:40], enviado_por=usuario,
        )
    documento.ordem = ordem
    documento.situacao = DocumentoOrdemServico.Situacao.CRIADA
    documento.leitura = _para_guardar(leitura)
    if novo:
        _salvar_com_arquivo(documento, leitura["arquivo"], conteudo)
    else:
        documento.save()
    return {"ordem": ordem, "documento": documento, "cliente": cliente, "cliente_novo": cliente_novo,
            "avisos": avisos}


def _para_guardar(leitura: dict) -> dict:
    """O que fica no banco: a leitura sem os candidatos do cadastro (são de agora)."""
    guardada = dict(leitura)
    guardada["cliente"] = {k: v for k, v in leitura["cliente"].items() if k != "escolha"}
    return guardada


def _salvar_com_arquivo(documento, nome: str, conteudo: bytes):
    """Guarda o arquivo no cofre e o registro; se o registro não entra, o arquivo sai.

    O arquivo vai para o armazenamento antes do INSERT (é o FileField que
    manda). Quando o INSERT falha -- o mesmo documento chegando duas vezes
    ao mesmo tempo bate no índice único do SHA-256 --, o arquivo que acabou
    de subir não pode ficar órfão no cofre.
    """
    documento.arquivo.save(nome, ContentFile(conteudo), save=False)
    try:
        documento.save()
    except Exception:
        try:
            documento.arquivo.delete(save=False)
        except Exception:  # noqa: BLE001 -- o erro que importa é o do banco
            logger.exception("Documento de O.S.: arquivo órfão não apagado (%s)", documento.arquivo.name)
        raise


def _guardar_pendente(request, leitura, *, lido, conteudo, documento=None):
    from ..models import DocumentoOrdemServico

    novo = documento is None
    if novo:
        documento = DocumentoOrdemServico(
            formato=lido["formato"], nome_arquivo=leitura["arquivo"][:150], tamanho_arquivo=len(conteudo),
            sha256=lido["sha256"], texto_sha256=lido.get("texto_sha256", ""),
            numero_no_documento=leitura["os"].get("numero", "")[:40], enviado_por=request.user,
        )
    documento.situacao = DocumentoOrdemServico.Situacao.PENDENTE
    documento.leitura = _para_guardar(leitura)
    if novo:
        _salvar_com_arquivo(documento, leitura["arquivo"], conteudo)
    else:
        documento.save()
    return documento


# ======================================================================
# A ENTRADA: UM ARQUIVO POR PEDIDO
# ======================================================================
def importar(request, nome: str, conteudo: bytes) -> dict:
    """Lê um documento e cria a O.S. -- ou diz o que falta, o que repete, o que não deu."""
    nome = (nome or "documento").strip()[:150]
    try:
        lido = arq.ler(nome, conteudo)
    except arq.ArquivoRecusado as exc:
        return {"estado": "ilegivel", "arquivo": nome, "motivo": str(exc)}
    except Exception:  # noqa: BLE001 -- arquivo estranho nunca derruba o lote
        logger.exception("Automatizador da O.S.: leitura de %s quebrou", nome)
        return {"estado": "ilegivel", "arquivo": nome,
                "motivo": "Não consegui ler este arquivo. Abra no Word, salve de novo e envie a cópia."}

    ctx = contexto.carregar()
    leitura = montar(nome, lido, hoje=timezone.localdate(), ctx=ctx)
    repetido, como = procurar_repetido(lido, leitura["os"]["numero"], leitura["os"]["numero_do_painel"])
    if repetido is not None and not isinstance(repetido, list):
        return _resposta_do_repetido(repetido, como, nome)

    existente = resolver_cliente(leitura)
    if isinstance(repetido, list) and repetido:
        mesmo = _mesmo_cliente_do_numero(repetido, leitura, existente)
        if mesmo is not None:
            return _resposta_do_repetido(mesmo, "o mesmo número de O.S. com o mesmo cliente", nome)

    return _criar_ou_guardar(request, leitura, existente, lido=lido, conteudo=conteudo)


def _criar_ou_guardar(request, leitura, existente, *, lido=None, conteudo=None, documento=None):
    from ..models import DocumentoOrdemServico

    faltas = pendencias(leitura)
    if not faltas:
        try:
            with transaction.atomic():
                criado = _criar_ordem(request, leitura, existente, documento=documento,
                                      conteudo=conteudo, lido=lido)
        except ErroDeFormulario as exc:
            # O cadastro de clientes tem a última palavra (nome repetido,
            # e-mail de outro cliente): a O.S. espera a pessoa decidir.
            leitura["cliente"]["vinculo"] = {
                "modo": "erro", "motivo": str(exc),
                "candidatos": (leitura["cliente"].get("vinculo") or {}).get("candidatos", []),
            }
            faltas = pendencias(leitura)
        except IntegrityError:
            achado = DocumentoOrdemServico.objects.filter(sha256=(lido or {}).get("sha256", "")).first()
            if achado is not None:
                return _resposta_do_repetido(achado, "o mesmo arquivo", leitura["arquivo"])
            raise
        else:
            return resposta_criada(criado)
    try:
        with transaction.atomic():
            documento = _guardar_pendente(request, leitura, lido=lido, conteudo=conteudo, documento=documento)
    except IntegrityError:
        achado = DocumentoOrdemServico.objects.filter(sha256=(lido or {}).get("sha256", "")).first()
        if achado is not None:
            return _resposta_do_repetido(achado, "o mesmo arquivo", leitura["arquivo"])
        raise
    return resposta_pendente(documento, leitura, faltas)


# ======================================================================
# COMPLETAR NA FOLHA
# ======================================================================
def completar(request, documento, post) -> dict:
    """Aplica o que a pessoa preencheu na folha e tenta criar de novo."""
    from ..models import DocumentoOrdemServico

    if documento.situacao != DocumentoOrdemServico.Situacao.PENDENTE:
        return _resposta_do_repetido(documento, "já criada", documento.nome_arquivo)
    leitura = dict(documento.leitura or {})
    if leitura.get("versao") != VERSAO:
        return {"estado": "ilegivel", "arquivo": documento.nome_arquivo, "documento": documento.pk,
                "motivo": "Esta leitura é de uma versão antiga. Descarte e envie o documento de novo."}
    leitura["os"] = dict(leitura["os"])
    leitura["cliente"] = dict(leitura["cliente"])
    leitura["itens"] = [dict(i) for i in leitura.get("itens") or []]
    erros = aplicar_envio(leitura, post)
    existente = resolver_cliente(leitura)
    if erros:
        faltas = pendencias(leitura)
        documento.leitura = _para_guardar(leitura)
        documento.save(update_fields=["leitura", "atualizado"])
        return resposta_pendente(documento, leitura, faltas, erros=erros)
    return _criar_ou_guardar(request, leitura, existente, documento=documento)


def aplicar_envio(leitura: dict, post) -> list[str]:
    """Os campos da folha (só os que faltavam) sobre a leitura guardada."""
    erros = []
    dados = leitura["cliente"]
    os_ = leitura["os"]
    escolha = (post.get("cliente_escolha") or "").strip()
    if escolha:
        if escolha.startswith("id:"):
            dados["escolha"] = {"modo": "existente", "cliente_id": escolha[3:]}
        elif escolha in ("novo", "sem_cadastro"):
            dados["escolha"] = {"modo": escolha}
    for campo, limite in (("nome", 90), ("telefone", 24), ("email", 150)):
        chave_post = f"cliente_{campo}"
        if chave_post in post:
            valor = det.espacos(post.get(chave_post) or "")[:limite]
            if campo == "telefone" and valor:
                from ..importacao_word.formulario import whatsapp_padrao

                valor = det.formatar_telefone(valor)
                dados["whatsapp"] = whatsapp_padrao(valor) == "sim"
            if campo == "email":
                valor = valor.lower()
            dados[campo] = valor
    for campo, limite in (("equipamento", 180), ("defeito_relatado", 4000), ("servico_executado", 4000)):
        if campo in post:
            valor = (post.get(campo) or "").strip()[:limite]
            if valor:
                os_[campo] = valor
    if "itens_valores" in post:
        import json

        try:
            linhas = json.loads(post.get("itens_valores") or "[]")
        except ValueError:
            linhas = []
            erros.append("Não consegui ler os valores das linhas.")
        for indice, valores in enumerate(linhas if isinstance(linhas, list) else []):
            if indice >= len(leitura["itens"]) or not isinstance(valores, dict):
                continue
            item = leitura["itens"][indice]
            quantidade = str(valores.get("quantidade") or "").strip()
            if quantidade:
                if quantidade.isdigit() and 0 < int(quantidade) <= 99999999:
                    item["quantidade"] = int(quantidade)
                    item["recusa"] = ""
                else:
                    erros.append(f"Linha {indice + 1}: a quantidade é um número inteiro maior que zero.")
            unitario = str(valores.get("valor_unitario") or "").strip()
            if unitario:
                lido = det.valor_do_campo(unitario)
                if lido is None or lido > LIMITE_DINHEIRO:
                    erros.append(f"Linha {indice + 1}: o valor “{unitario}” não é um valor em reais.")
                else:
                    item["valor_unitario"] = _texto_dinheiro(lido)
    for campo in ("frete", "desconto"):
        if campo in post:
            bruto = (post.get(campo) or "").strip()
            if not bruto:
                os_[campo] = ""
                continue
            lido = det.valor_do_campo(bruto)
            if lido is None:
                erros.append(f"{campo.capitalize()}: “{bruto}” não é um valor em reais.")
            else:
                os_[campo] = _texto_dinheiro(lido)
    if post.get("usar_total") == "linha" and os_.get("total_documento") and not leitura["itens"]:
        leitura["itens"].append({
            "tipo": "servico", "descricao": "Serviço", "quantidade": 1,
            "valor_unitario": os_["total_documento"], "peca_id": None, "preco_catalogo": False,
            "recusa": "", "fonte": "", "como": "folha",
        })
    if post.get("usar_total") == "desconto" and os_.get("total_documento"):
        conta = contas(dict(leitura, os=dict(os_, desconto="")))
        total = _dinheiro(os_["total_documento"])
        if conta["completos"] and total is not None and conta["itens"] + conta["frete"] >= total:
            os_["desconto"] = _texto_dinheiro(conta["itens"] + conta["frete"] - total)
    if post.get("ignorar_total") == "1":
        os_["total_documento"] = ""
        os_["subtotal_documento"] = ""
    return erros


def descartar(documento) -> dict:
    from ..models import DocumentoOrdemServico

    if documento.situacao != DocumentoOrdemServico.Situacao.PENDENTE:
        return {"estado": "erro", "motivo": "Só se descarta o documento que ainda não virou O.S."}
    nome = documento.nome_arquivo
    documento.delete()
    return {"estado": "descartado", "arquivo": nome}


# ======================================================================
# AS RESPOSTAS (o que a folha desenha)
# ======================================================================
URLS = "sistema_interno.urls"


def link_da_ordem(ordem) -> str:
    """A tela de O.S. filtrada nesta O.S., com a janela dela aberta (os-automatizador.js)."""
    from urllib.parse import urlencode

    return (f"{reverse('ordens_servico_inner', urlconf=URLS)}?"
            f"{urlencode({'q': ordem.numero_documento, 'abrir_os': ordem.pk})}")


def _resumo_da_ordem(ordem) -> dict:
    return {
        "id": ordem.pk, "numero": ordem.numero_documento, "link": link_da_ordem(ordem),
        "previa": reverse("ordem_servico_previa_inner", args=[ordem.pk], urlconf=URLS),
        "cliente": ordem.destinatario if ordem.cliente_id or ordem.nome_cliente else "Sem cliente",
        "equipamento": ordem.equipamento, "situacao": ordem.get_status_display(),
        "total": brl(ordem.total),
    }


def resposta_criada(criado: dict) -> dict:
    ordem = criado["ordem"]
    documento = criado["documento"]
    cliente = criado["cliente"]
    resposta = {
        "estado": "criada", "arquivo": documento.nome_arquivo, "formato": documento.formato,
        "documento": documento.pk, "os": _resumo_da_ordem(ordem), "avisos": criado["avisos"],
        "resumo": resumo(documento.leitura, ordem=ordem),
        "arquivo_url": reverse("documento_ordem_servico_arquivo", args=[documento.pk], urlconf=URLS),
    }
    if cliente is not None:
        resposta["cliente"] = {"id": cliente.pk, "nome": cliente.nome_cliente, "novo": criado["cliente_novo"]}
    return resposta


def _resposta_do_repetido(achado, como: str, nome: str) -> dict:
    from ..models import DocumentoOrdemServico, OrdemServico

    if isinstance(achado, OrdemServico):
        return {"estado": "repetida", "arquivo": nome, "os": _resumo_da_ordem(achado),
                "motivo": f"Este documento é a {achado.numero_documento}, que já está no painel."}
    if achado.situacao == DocumentoOrdemServico.Situacao.PENDENTE:
        leitura = achado.leitura or {}
        return resposta_pendente(achado, leitura, pendencias_guardadas(leitura),
                                 recado=f"Este documento já foi lido ({como}) e está esperando completar.")
    if achado.ordem_id is None:
        return {"estado": "repetida", "arquivo": nome, "motivo": "Este documento já foi importado."}
    ordem = achado.ordem
    return {"estado": "repetida", "arquivo": nome, "os": _resumo_da_ordem(ordem),
            "motivo": f"Já importado ({como}) na {ordem.numero_documento}."}


def pendencias_guardadas(leitura: dict) -> list[dict]:
    if not leitura.get("os"):
        return [{"campo": "arquivo", "rotulo": "Documento", "motivo": "leitura vazia: envie de novo"}]
    return pendencias(leitura)


_ROTULO_TIPO = {"manutencao": "Manutenção", "instalacao": "Instalação", "revisao": "Revisão preventiva",
                "visita": "Visita técnica", "outro": "Outro serviço"}
_ROTULO_STATUS = {
    "aguardando_resposta": "Aguardando ciência", "aberta": "Aberta", "agendada": "Agendada",
    "em_execucao": "Em execução", "aguardando_peca": "Aguardando peça", "concluida": "Concluída",
    "cancelada": "Cancelada",
}
_ROTULO_PRIORIDADE = {"baixa": "Baixa", "normal": "Normal", "alta": "Alta", "urgente": "Urgente"}


def resumo(leitura: dict, *, ordem=None) -> list[dict]:
    """O que foi lido, numa lista curta para a linha do documento."""
    os_ = leitura.get("os") or {}
    dados = leitura.get("cliente") or {}
    vinculo = dados.get("vinculo") or {}
    linhas = []
    nome_cliente = vinculo.get("nome") or dados.get("nome") or dados.get("estabelecimento")
    if nome_cliente:
        como = {"existente": "do cadastro", "novo": "cadastro novo", "sem_cadastro": "sem cadastro",
                "falta": "falta o contato" if dados.get("nome") else "falta o nome",
                "erro": "ver abaixo"}.get(vinculo.get("modo"), "confirmar")
        linhas.append({"rotulo": "Cliente", "valor": nome_cliente, "como": como})
    contato = " · ".join(p for p in (dados.get("telefone"), dados.get("email")) if p)
    if contato:
        linhas.append({"rotulo": "Contato", "valor": contato, "como": ""})
    if os_.get("equipamento"):
        linhas.append({"rotulo": "Equipamento", "valor": os_["equipamento"],
                       "como": "pelo catálogo" if os_.get("equipamento_como") == "catalogo" else ""})
    if os_.get("numero_serie"):
        linhas.append({"rotulo": "Série", "valor": os_["numero_serie"], "como": ""})
    for campo, rotulo in (("defeito_relatado", "Defeito"), ("diagnostico", "Diagnóstico"),
                          ("servico_executado", "Serviço executado")):
        if os_.get(campo):
            texto = os_[campo].replace("\n", " ")
            linhas.append({"rotulo": rotulo, "valor": texto[:140] + ("…" if len(texto) > 140 else ""), "como": ""})
    linhas.append({"rotulo": "Tipo", "valor": _ROTULO_TIPO.get(os_.get("tipo"), "Manutenção"), "como": ""})
    situacao = ordem.get_status_display() if ordem is not None else _ROTULO_STATUS.get(os_.get("status"), "")
    if situacao:
        linhas.append({"rotulo": "Situação", "valor": situacao,
                       "como": "" if os_.get("status_como") in ("documento", "") else os_.get("status_como", "")})
    if os_.get("prioridade") and os_["prioridade"] != "normal":
        linhas.append({"rotulo": "Prioridade", "valor": _ROTULO_PRIORIDADE.get(os_["prioridade"], ""), "como": ""})
    if os_.get("tecnico_nome"):
        linhas.append({"rotulo": "Técnico", "valor": os_["tecnico_nome"],
                       "como": "" if os_.get("tecnico_id") else "fora da equipe"})
    for campo, rotulo in (("data_documento", "Documento de"), ("agendada_para", "Agendada para"),
                          ("concluida_em", "Concluída em"), ("garantia_ate", "Garantia até")):
        if os_.get(campo):
            linhas.append({"rotulo": rotulo, "valor": _data_br(os_[campo]), "como": ""})
    itens = leitura.get("itens") or []
    if itens or os_.get("total_documento"):
        conta = contas(leitura)
        quantos = f"{len(itens)} linha" + ("s" if len(itens) != 1 else "")
        valor = brl(ordem.total) if ordem is not None else (brl(conta["total"]) if conta["completos"] else "—")
        linhas.append({"rotulo": "Itens", "valor": f"{quantos} · {valor}" if itens else valor, "como": ""})
    return linhas


def resposta_pendente(documento, leitura: dict, faltas: list[dict], *, erros=(), recado="") -> dict:
    """A linha "Falta completar": o que achou, e os campos só do que falta, já preenchidos."""
    os_ = leitura.get("os") or {}
    dados = leitura.get("cliente") or {}
    vinculo = dados.get("vinculo") or {}
    campos_folha = []
    for falta in faltas:
        campo = falta["campo"]
        if campo == "cliente":
            campos_folha.append({
                "campo": "cliente", "rotulo": "Cliente", "motivo": falta["motivo"],
                "candidatos": vinculo.get("candidatos") or [],
                "valores": {"nome": dados.get("nome", ""), "telefone": dados.get("telefone", ""),
                            "email": dados.get("email", "")},
                "pode_sem_cadastro": True,
            })
        elif campo in ("equipamento", "defeito_relatado", "servico_executado"):
            campos_folha.append({"campo": campo, "rotulo": falta["rotulo"], "motivo": falta["motivo"],
                                 "valor": os_.get(campo, "")})
        elif campo == "valores":
            conta = contas(leitura)
            total_documento = _dinheiro(os_.get("total_documento"))
            diferenca = None
            if total_documento is not None and conta["completos"] and conta["itens"] + conta["frete"] > total_documento:
                diferenca = conta["itens"] + conta["frete"] - total_documento
            campos_folha.append({
                "campo": "valores", "rotulo": "Valores", "motivo": falta["motivo"],
                "itens": [
                    {"descricao": i["descricao"], "tipo": i["tipo"],
                     "quantidade": i.get("quantidade") or "",
                     "valor_unitario": det.moeda(_dinheiro(i.get("valor_unitario")))
                     if _dinheiro(i.get("valor_unitario")) is not None else "",
                     "recusa": i.get("recusa", "")}
                    for i in leitura.get("itens") or []
                ],
                "frete": det.moeda(_dinheiro(os_.get("frete"))) if os_.get("frete") else "",
                "desconto": det.moeda(_dinheiro(os_.get("desconto"))) if os_.get("desconto") else "",
                "total_documento": brl(total_documento) if total_documento is not None else "",
                "diferenca": brl(diferenca) if diferenca is not None else "",
                "lancar_total": bool(total_documento is not None and not leitura.get("itens")),
            })
        else:
            campos_folha.append({"campo": campo, "rotulo": falta["rotulo"], "motivo": falta["motivo"]})
    return {
        "estado": "falta", "arquivo": documento.nome_arquivo, "formato": documento.formato,
        "documento": documento.pk, "faltas": campos_folha, "avisos": leitura.get("avisos") or [],
        "resumo": resumo(leitura), "erros": list(erros), "recado": recado,
        "enviado_em": timezone.localtime(documento.criacao).strftime("%d/%m/%Y %H:%M") if documento.criacao else "",
    }


def pendentes(limite: int = 20) -> list[dict]:
    """Os documentos que esperam completar (de qualquer pessoa da equipe)."""
    from ..models import DocumentoOrdemServico

    saida = []
    for documento in DocumentoOrdemServico.objects.filter(
        situacao=DocumentoOrdemServico.Situacao.PENDENTE,
    ).order_by("-criacao", "-id")[:limite]:
        leitura = documento.leitura or {}
        saida.append(resposta_pendente(documento, leitura, pendencias_guardadas(leitura)))
    return saida
