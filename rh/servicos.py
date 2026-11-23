"""O que as telas do RH fazem além de mostrar: trilha, pasta e painel."""

from __future__ import annotations

from datetime import timedelta

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from core.registro_cadastro import ip_da_requisicao

from .arquivos import ArquivoConferido
from .models import (
    COM_VALIDADE_OBRIGATORIA,
    OBRIGATORIOS,
    AjustePonto,
    Colaborador,
    DocumentoColaborador,
    RegistroRH,
    Situacao,
    Tarefa,
    TipoDocumento,
)

#: "Vencendo" no painel: de hoje até daqui a 30 dias.
JANELA_DE_VENCIMENTO = 30


# ======================================================================
# TRILHA DE AUDITORIA
# ======================================================================
def registrar(request, acao, *, colaborador=None, documento=None, descricao=""):
    usuario = getattr(request, "user", None)
    autenticado = bool(getattr(usuario, "is_authenticated", False))
    ip, _ = ip_da_requisicao(request) if request is not None else (None, "")
    return RegistroRH.objects.create(
        usuario=usuario if autenticado else None,
        usuario_nome=(
            (usuario.get_full_name() or usuario.get_username()) if autenticado else "sem login"
        )[:150],
        acao=acao,
        colaborador=colaborador,
        documento=documento,
        descricao=(descricao or "")[:300],
        ip=ip,
        navegador=(request.META.get("HTTP_USER_AGENT", "") if request is not None else "")[:300],
    )


# ======================================================================
# A FICHA E A PRODUÇÃO
# ======================================================================
def ligar_na_producao(colaborador: Colaborador):
    """O nome da pessoa na lista da montagem (sistema_interno.Colaborador).

    As ordens de produção já escolhem "quem está montando" numa lista de
    nomes sem conta. A ficha do RH aponta para esse nome -- o mesmo, se já
    existir com o nome igual e livre; senão, um novo --, e o desligamento
    o tira da lista. Assim há UM cadastro, e "Minhas tarefas" acha as ordens.
    """
    from sistema_interno.models import Colaborador as NomeNaProducao

    ativo = colaborador.situacao != Situacao.DESLIGADO
    if colaborador.colaborador_producao_id:
        nome = colaborador.colaborador_producao
        mudou = nome.ativo != ativo
        nome.ativo = ativo
        if mudou:
            nome.save(update_fields=["ativo", "atualizado"])
        return nome
    if colaborador.setor != "producao":
        return None
    livre = (
        NomeNaProducao.objects.filter(nome__iexact=colaborador.nome[:90], ficha_rh__isnull=True)
        .order_by("id").first()
    )
    nome = livre or NomeNaProducao.objects.create(nome=colaborador.nome[:90], ativo=ativo)
    if livre and livre.ativo != ativo:
        livre.ativo = ativo
        livre.save(update_fields=["ativo", "atualizado"])
    Colaborador.objects.filter(pk=colaborador.pk).update(colaborador_producao=nome)
    colaborador.colaborador_producao = nome
    return nome


# ======================================================================
# DOCUMENTOS
# ======================================================================
def guardar_documento(colaborador, conferido: ArquivoConferido, *, tipo, descricao="", emissao=None,
                      validade=None, usuario=None) -> DocumentoColaborador:
    """Grava o arquivo no armazenamento privado e a linha no banco.

    Tudo-ou-nada: se o banco falhar depois do arquivo subir, o arquivo é
    apagado (o `on_commit` do sinal não chega a rodar).
    """
    documento = DocumentoColaborador(
        colaborador=colaborador,
        tipo=tipo,
        descricao=(descricao or "").strip()[:120],
        nome_original=conferido.nome_original,
        tipo_conteudo=conferido.tipo_conteudo,
        tamanho=conferido.tamanho,
        sha256=conferido.sha256,
        emissao=emissao,
        validade=validade,
        enviado_por=usuario if getattr(usuario, "is_authenticated", False) else None,
    )
    documento.full_clean(exclude=["arquivo"])
    documento.arquivo.save("documento" + conferido.extensao, ContentFile(conferido.dados), save=False)
    try:
        with transaction.atomic():
            documento.save()
    except Exception:
        documento.arquivo.storage.delete(documento.arquivo.name)
        raise
    return documento


def mais_recentes(documentos):
    """O documento que vale de cada tipo: o último enviado."""
    vale = {}
    for doc in sorted(documentos, key=lambda d: (d.enviado_em, d.pk)):
        vale[doc.tipo] = doc
    return vale


def checklist(colaborador, documentos=None):
    """O que a pasta precisa ter, pelo vínculo, e o que FALTA.

    Cada linha: tipo, rótulo, documento que vale (ou None) e o estado:
    "ok", "falta", "vencido", "vence" (nos próximos 30 dias) ou "antigo"
    (comprovante de residência com mais de 90 dias -- só sinaliza).
    """
    documentos = list(colaborador.documentos.all()) if documentos is None else documentos
    vale = mais_recentes(documentos)
    linhas = []
    for tipo in OBRIGATORIOS.get(colaborador.vinculo, ()):
        doc = vale.get(tipo)
        if doc is None:
            estado = "falta"
        elif doc.vencido:
            estado = "vencido"
        elif doc.dias_para_vencer is not None and doc.dias_para_vencer <= JANELA_DE_VENCIMENTO:
            estado = "vence"
        elif doc.residencia_antiga:
            estado = "antigo"
        else:
            estado = "ok"
        linhas.append({
            "tipo": tipo,
            "rotulo": TipoDocumento(tipo).label,
            "documento": doc,
            "estado": estado,
            "validade_obrigatoria": tipo in COM_VALIDADE_OBRIGATORIA,
        })
    return linhas


def faltando(colaborador, documentos=None):
    return [linha for linha in checklist(colaborador, documentos) if linha["estado"] in ("falta", "vencido")]


def documentos_a_vencer(dias=JANELA_DE_VENCIMENTO, hoje=None):
    """Documentos que VALEM (o último enviado de cada tipo) vencidos ou vencendo.

    Um ASO renovado substitui o vencido: só o mais novo de cada tipo conta.
    """
    hoje = hoje or timezone.localdate()
    limite = hoje + timedelta(days=dias)
    tipos_que_vencem = (
        DocumentoColaborador.objects.filter(validade__isnull=False)
        .exclude(colaborador__situacao=Situacao.DESLIGADO)
        .values_list("colaborador_id", "tipo").distinct()
    )
    pares = set(tipos_que_vencem)
    if not pares:
        return []
    candidatos = (
        DocumentoColaborador.objects.filter(
            colaborador_id__in={c for c, _ in pares}, tipo__in={t for _, t in pares},
        )
        .select_related("colaborador")
        .order_by("enviado_em", "id")
    )
    vale = {}
    for doc in candidatos:
        vale[(doc.colaborador_id, doc.tipo)] = doc
    resultado = [
        doc for chave, doc in vale.items()
        if chave in pares and doc.validade and doc.validade <= limite
    ]
    resultado.sort(key=lambda d: (d.validade, d.colaborador.nome))
    return resultado


def fichas_com_pendencia():
    """Colaboradores (não desligados) com documento obrigatório faltando ou vencido."""
    pessoas = list(
        Colaborador.objects.exclude(situacao=Situacao.DESLIGADO).prefetch_related("documentos")
    )
    resultado = []
    for pessoa in pessoas:
        falta = faltando(pessoa, list(pessoa.documentos.all()))
        if falta:
            resultado.append((pessoa, falta))
    return resultado


# ======================================================================
# O PAINEL DO RH
# ======================================================================
def painel(agora=None):
    from . import ponto, termo

    hoje = timezone.localdate(agora)
    vencendo = documentos_a_vencer(hoje=hoje)
    return {
        "hoje": ponto.situacao_de_hoje(agora),
        "ajustes_pendentes": list(
            AjustePonto.objects.filter(situacao=AjustePonto.Estado.PENDENTE)
            .select_related("colaborador", "marcacao").order_by("data", "id")[:8]
        ),
        "total_ajustes": AjustePonto.objects.filter(situacao=AjustePonto.Estado.PENDENTE).count(),
        "vencendo": vencendo[:8],
        "total_vencendo": len(vencendo),
        "atrasadas": list(
            Tarefa.objects.filter(prazo__lt=hoje).exclude(situacao=Tarefa.Estado.FEITA)
            .select_related("colaborador").order_by("prazo")[:8]
        ),
        "total_atrasadas": Tarefa.objects.filter(prazo__lt=hoje).exclude(situacao=Tarefa.Estado.FEITA).count(),
        "termo_pendentes": termo.pendentes().count(),
        "total_ativos": Colaborador.objects.exclude(situacao=Situacao.DESLIGADO).count(),
        "ponto": alertas_do_ponto(agora),
    }


def alertas_do_ponto(agora=None):
    """O que o ponto da equipe pede de atenção, para o Início do RH (seção 125).

    O período é o do último cartão do relógio importado; sem cartão, o mês
    até ontem. Os espelhos saem em lote (ponto.espelhos): quatro consultas
    para a equipe inteira, não quatro por pessoa.
    """
    from datetime import timedelta as _dias

    from . import ponto
    from .models import CartaoPonto

    hoje = timezone.localdate(agora)
    ultimo = (
        CartaoPonto.objects.filter(situacao=CartaoPonto.Estado.IMPORTADO)
        .order_by("-fim", "-inicio").values_list("inicio", "fim").first()
    )
    pendentes = CartaoPonto.objects.filter(situacao=CartaoPonto.Estado.PENDENTE).count()
    if ultimo:
        de, ate, origem = ultimo[0], ultimo[1], "cartao"
    else:
        de, ate, origem = hoje.replace(day=1), hoje - _dias(days=1), "mes"
    vazio = {"de": de, "ate": ate, "origem": origem, "linhas": [], "total": 0, "pendentes_importacao": pendentes,
             "query": f"de={de:%Y-%m-%d}&ate={ate:%Y-%m-%d}"}
    if ate < de:
        return vazio
    pessoas = list(Colaborador.objects.exclude(situacao=Situacao.DESLIGADO).order_by("nome"))
    todos = ponto.espelhos(pessoas, de, ate, agora=agora)
    linhas = []
    for pessoa in pessoas:
        importantes = [a for a in todos[pessoa.pk].alertas if a["nivel"] in ("perigo", "alerta")]
        if importantes:
            peso = sum(2 if a["nivel"] == "perigo" else 1 for a in importantes)
            linhas.append({"c": pessoa, "alertas": importantes, "peso": peso})
    linhas.sort(key=lambda linha: (-linha["peso"], linha["c"].nome))
    vazio.update({"linhas": linhas[:8], "total": len(linhas)})
    return vazio
