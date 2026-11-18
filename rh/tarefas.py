"""Tarefas e o ponto de ligação com a PRODUÇÃO (e com o resto do sistema).

O RH não importa nada da produção. Quem cria trabalho para alguém -- a
lista de produção com as 7 etapas de cada unidade, um pedido, uma O.S. --
chama daqui:

    from rh.tarefas import atribuir, sugerir_responsaveis, concluir

    # quem sugerir para a etapa "Adesivo" (Engenharia de produção com a
    # especialidade Adesivo primeiro, os menos ocupados antes)
    candidatos = sugerir_responsaveis("Adesivo")

    # dar a etapa a alguém (ou, com colaborador=None, ao primeiro sugerido)
    tarefa = atribuir(candidatos[0], etapa_da_unidade, etapa="Adesivo",
                      prazo=date(2026, 11, 30), rotulo="Unidade 12 · Air Game",
                      url="/producao/...")

    # a etapa terminou na produção: a tarefa vira "feita"
    concluir(etapa_da_unidade, etapa="Adesivo")

A ligação é uma chave genérica (ContentType + id): a tarefa aponta para a
coisa que a originou, seja ela qual for. Uma coisa + etapa tem no máximo
UMA tarefa: chamar `atribuir` de novo troca o responsável (e o prazo), em
vez de duplicar. "Minhas tarefas" mostra as avulsas e as que vieram daqui
juntas, e -- enquanto a lista de produção nova não chega -- também as
ordens de produção abertas em que a pessoa é o colaborador da montagem.

Os sinais `tarefa_atribuida` e `tarefa_mudou` avisam quem quiser ouvir
(a produção pode marcar a etapa como feita quando a pessoa conclui a
tarefa pelo celular).
"""

from __future__ import annotations

import unicodedata

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Count, Q
from django.dispatch import Signal

from .models import Colaborador, Especialidade, Setor, Situacao, Tarefa

tarefa_atribuida = Signal()  # sender=Tarefa, tarefa=, objeto=, criada=
tarefa_mudou = Signal()      # sender=Tarefa, tarefa=, situacao=, anterior=, por=

#: As 7 etapas por que passa cada brinquedo (e o estoque), no nome que a
#: produção usa, para a especialidade de quem as faz.
ETAPAS_DA_PRODUCAO = (
    "Corte de MDF", "Montagem", "Adesivo", "Eletrônica", "Finalização",
    "Teste de qualidade", "Embalagem",
)
_ETAPA_PARA_ESPECIALIDADE = {
    "corte de mdf": Especialidade.CORTE,
    "corte": Especialidade.CORTE,
    "montagem": Especialidade.MONTAGEM,
    "adesivo": Especialidade.ADESIVO,
    "adesivagem": Especialidade.ADESIVO,
    "eletronica": Especialidade.ELETRONICA,
    "finalizacao": Especialidade.FINALIZACAO,
    "teste de qualidade": Especialidade.TESTE,
    "teste": Especialidade.TESTE,
    "qualidade": Especialidade.TESTE,
    "embalagem": Especialidade.EMBALAGEM,
    "estoque": Especialidade.ESTOQUE,
    "materia-prima": Especialidade.ESTOQUE,
    "materia prima": Especialidade.ESTOQUE,
}


def _sem_acento(texto: str) -> str:
    texto = unicodedata.normalize("NFD", str(texto or ""))
    return "".join(c for c in texto if unicodedata.category(c) != "Mn").lower().strip()


def nome_da_etapa(etapa) -> str:
    """Aceita o texto ("Adesivo") ou um objeto de etapa (usa `nome`, senão str())."""
    if etapa is None:
        return ""
    nome = getattr(etapa, "nome", None) or getattr(etapa, "titulo", None) or str(etapa)
    return str(nome).strip()[:60]


def especialidade_da_etapa(etapa) -> str | None:
    return _ETAPA_PARA_ESPECIALIDADE.get(_sem_acento(nome_da_etapa(etapa)))


def setor_da_etapa(etapa) -> str | None:
    return Setor.PRODUCAO if especialidade_da_etapa(etapa) else None


def sugerir_responsaveis(etapa=None, *, setor=None, limite=6):
    """Quem pode fazer a etapa, do mais indicado ao menos.

    Primeiro quem é do setor E tem a especialidade da etapa; depois o resto
    do setor. Dentro de cada grupo, quem tem menos tarefas abertas vem
    antes. Só gente ativa.
    """
    especialidade = especialidade_da_etapa(etapa)
    setor = setor or setor_da_etapa(etapa)
    consulta = Colaborador.objects.filter(situacao=Situacao.ATIVO)
    if setor:
        consulta = consulta.filter(setor=setor)
    consulta = consulta.annotate(
        abertas=Count("tarefas", filter=~Q(tarefas__situacao=Tarefa.Estado.FEITA)),
    )
    pessoas = list(consulta)

    def ordem(c):
        especialista = bool(especialidade and especialidade in (c.especialidades or []))
        return (0 if especialista else 1, c.abertas, c.nome)

    pessoas.sort(key=ordem)
    for c in pessoas:
        c.especialista = bool(especialidade and especialidade in (c.especialidades or []))
    return pessoas[:limite] if limite else pessoas


def _tipo_e_id(objeto):
    tipo = ContentType.objects.get_for_model(objeto, for_concrete_model=True)
    return tipo, objeto.pk


def atribuir(colaborador, objeto, etapa=None, prazo=None, *, titulo=None, descricao="",
             prioridade=Tarefa.Prioridade.NORMAL, por=None, rotulo=None, url=""):
    """Dá a `objeto` (e à `etapa`, se houver) a um colaborador.

    `colaborador` pode ser um Colaborador, o id dele, ou None (vai para o
    primeiro sugerido para a etapa; sem ninguém, a tarefa fica sem dono e
    aparece para a Gestão). Devolve a Tarefa (criada ou atualizada).
    """
    if colaborador is not None and not isinstance(colaborador, Colaborador):
        colaborador = Colaborador.objects.get(pk=colaborador)
    if colaborador is None:
        sugeridos = sugerir_responsaveis(etapa, limite=1)
        colaborador = sugeridos[0] if sugeridos else None
    if colaborador is not None and colaborador.situacao == Situacao.DESLIGADO:
        raise ValueError("Não dá para atribuir tarefa a quem foi desligado.")

    tipo, ident = _tipo_e_id(objeto)
    nome_etapa = nome_da_etapa(etapa)
    rotulo = (rotulo or str(objeto) or "").strip()[:200]
    with transaction.atomic():
        tarefa = (
            Tarefa.objects.select_for_update()
            .filter(content_type=tipo, object_id=ident, etapa=nome_etapa)
            .first()
        )
        criada = tarefa is None
        if criada:
            tarefa = Tarefa(
                content_type=tipo,
                object_id=ident,
                etapa=nome_etapa,
                titulo=(titulo or (f"{nome_etapa} · {rotulo}" if nome_etapa else rotulo) or "Tarefa")[:160],
                descricao=descricao or "",
                prioridade=prioridade,
                setor=setor_da_etapa(etapa) or (colaborador.setor if colaborador else ""),
                criada_por=por if getattr(por, "is_authenticated", False) else None,
            )
        elif titulo:
            tarefa.titulo = titulo[:160]
        tarefa.colaborador = colaborador
        if prazo is not None:
            tarefa.prazo = prazo
        tarefa.origem_rotulo = rotulo
        if url:
            tarefa.origem_url = str(url)[:300]
        tarefa.save()
    tarefa_atribuida.send(sender=Tarefa, tarefa=tarefa, objeto=objeto, criada=criada)
    return tarefa


def tarefas_do_objeto(objeto):
    tipo, ident = _tipo_e_id(objeto)
    return Tarefa.objects.filter(content_type=tipo, object_id=ident).select_related("colaborador")


def mudar_situacao(tarefa: Tarefa, nova: str, *, por=None) -> Tarefa:
    anterior = tarefa.situacao
    if anterior == nova:
        return tarefa
    tarefa.mudar_situacao(nova)
    tarefa.save(update_fields=["situacao", "iniciada_em", "concluida_em", "atualizada_em"])
    tarefa_mudou.send(sender=Tarefa, tarefa=tarefa, situacao=nova, anterior=anterior, por=por)
    return tarefa


def concluir(objeto, etapa=None, *, por=None) -> int:
    """A coisa (ou a etapa dela) terminou lá na origem: as tarefas viram "feitas"."""
    consulta = tarefas_do_objeto(objeto).exclude(situacao=Tarefa.Estado.FEITA)
    if etapa is not None:
        consulta = consulta.filter(etapa=nome_da_etapa(etapa))
    total = 0
    for tarefa in consulta:
        mudar_situacao(tarefa, Tarefa.Estado.FEITA, por=por)
        total += 1
    return total


def ordens_de_producao_de(colaborador):
    """As ordens de produção abertas em que a pessoa é quem monta.

    É a ligação que já existe hoje (OrdemProducao.colaborador aponta para
    o nome da produção, `colaborador_producao` da ficha). Só leitura.
    """
    if not colaborador or not colaborador.colaborador_producao_id:
        return []
    try:
        from sistema_interno.models import OrdemProducao
    except ImportError:  # pragma: no cover -- a produção mudou de lugar
        return []
    abertas = [
        s for s in ("planejada", "producao", "pausada", "bloqueada")
        if s in OrdemProducao.Status.values
    ]
    return list(
        OrdemProducao.objects.filter(colaborador_id=colaborador.colaborador_producao_id, status__in=abertas)
        .select_related("produto").order_by("-id")[:20]
    )
