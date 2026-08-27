"""Funções combináveis da equipe e capacidades do painel interno.

Não existem subclasses de usuário. Cada integrante continua sendo um
``auth.User`` normal e recebe uma ou mais funções por meio dos ``Group`` do
Django. Isso permite, por exemplo, que a mesma pessoa seja Vendas e Gestão
sem duplicar conta ou criar uma hierarquia rígida.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth.models import Group


PRODUCAO = "Equipe · Produção"
CRIACAO = "Equipe · Criação do site"
VENDAS = "Equipe · Vendas"
AMBULANTE = "Equipe · Vendedor ambulante"
FINANCEIRO = "Equipe · Financeiro"
GESTAO = "Equipe · Gestão"


@dataclass(frozen=True)
class Funcao:
    codigo: str
    grupo: str
    titulo: str
    descricao: str
    icone: str


FUNCOES = (
    Funcao(
        "producao",
        PRODUCAO,
        "Engenharia de produção",
        "Estoque, materiais, fichas técnicas, etapas e ordens de produção.",
        "bi-hammer",
    ),
    Funcao(
        "criacao",
        CRIACAO,
        "Criação e site",
        "Catálogo, imagens, banners, projetos, eventos, promoções e vitrine.",
        "bi-palette2",
    ),
    Funcao(
        "vendas",
        VENDAS,
        "Vendas",
        "Clientes, propostas e acompanhamento do bloco comercial dos orçamentos.",
        "bi-file-earmark-text",
    ),
    Funcao(
        "ambulante",
        AMBULANTE,
        "Vendedor ambulante",
        "Visitas externas, clientes compartilhados e os próprios orçamentos.",
        "bi-geo-alt-fill",
    ),
    Funcao(
        "financeiro",
        FINANCEIRO,
        "Financeiro",
        "Vendas, pedidos, recebimentos, despesas e indicadores financeiros.",
        "bi-cash-stack",
    ),
    Funcao(
        "gestao",
        GESTAO,
        "Gestão",
        "Supervisão de indicadores, clientes, orçamentos e de todas as áreas.",
        "bi-graph-up-arrow",
    ),
)

FUNCOES_POR_CODIGO = {funcao.codigo: funcao for funcao in FUNCOES}
NOMES_DOS_GRUPOS = tuple(funcao.grupo for funcao in FUNCOES)


def grupos_de_funcoes():
    """Garante e devolve os grupos, sem depender de cadastro manual."""
    return {
        nome: Group.objects.get_or_create(name=nome)[0]
        for nome in NOMES_DOS_GRUPOS
    }


def nomes_das_funcoes(user) -> set[str]:
    if not getattr(user, "is_authenticated", False) or not user.is_active:
        return set()
    if user.is_superuser:
        return set(NOMES_DOS_GRUPOS)

    memorizadas = getattr(user, "_funcoes_interno_cache", None)
    if memorizadas is not None:
        return set(memorizadas)

    grupos_prefetched = getattr(user, "_prefetched_objects_cache", {}).get("groups")
    if grupos_prefetched is not None:
        nomes = {
            grupo.name for grupo in grupos_prefetched
            if grupo.name in NOMES_DOS_GRUPOS
        }
    else:
        nomes = set(
            user.groups.filter(name__in=NOMES_DOS_GRUPOS)
            .values_list("name", flat=True)
        )

    user._funcoes_interno_cache = frozenset(nomes)
    return nomes


def tem_funcao(user, *funcoes: str) -> bool:
    if getattr(user, "is_superuser", False) and user.is_active:
        return True
    return bool(nomes_das_funcoes(user).intersection(funcoes))


def faz_parte_da_equipe(user) -> bool:
    return bool(nomes_das_funcoes(user))


def capacidades(user) -> dict[str, bool]:
    """Permissões da interface e das views, calculadas no mesmo lugar."""
    superusuario = bool(
        getattr(user, "is_authenticated", False)
        and getattr(user, "is_active", False)
        and getattr(user, "is_superuser", False)
    )
    producao = tem_funcao(user, PRODUCAO)
    criacao = tem_funcao(user, CRIACAO)
    vendas = tem_funcao(user, VENDAS)
    ambulante = tem_funcao(user, AMBULANTE)
    funcao_financeiro = tem_funcao(user, FINANCEIRO)
    gestao = tem_funcao(user, GESTAO)
    comercial = vendas or ambulante or gestao
    acesso_financeiro = funcao_financeiro or gestao

    return {
        "superusuario": superusuario,
        "producao": producao,
        "criacao": criacao,
        "vendas": vendas,
        "ambulante": ambulante,
        "financeiro_funcao": funcao_financeiro,
        "gestao": gestao,
        "estoque": producao or gestao,
        "clientes": comercial,
        # Financeiro participa do mesmo orçamento, mas somente no bloco
        # de preço/condições. Criar a proposta e definir os itens continua
        # sendo responsabilidade comercial.
        "orcamentos": comercial or acesso_financeiro,
        "orcamentos_criar": comercial,
        "orcamentos_editar_comercial": comercial,
        "orcamentos_editar_financeiro": acesso_financeiro,
        # Uma conta exclusivamente Ambulante trabalha apenas a própria
        # carteira de propostas. Se também receber Vendas ou Gestão, passa
        # a participar da central compartilhada como essas funções preveem.
        "orcamentos_proprios": ambulante and not (vendas or gestao),
        # Vendas corrige o próprio rascunho; Gestão pode remover qualquer
        # rascunho. Clientes não têm autoria, então a exclusão fica com
        # Gestão. O estado do orçamento ainda é conferido por objeto abaixo.
        "excluir_clientes": gestao,
        "excluir_orcamentos": comercial,
        "excluir_orcamentos_alheios": gestao,
        "financeiro": acesso_financeiro,
        "vendas_financeiro": acesso_financeiro,
        "pedidos": acesso_financeiro,
        "manutencoes": producao or gestao,
        "ordens_servico": producao or acesso_financeiro or gestao,
        "ordens_servico_editar": producao or gestao,
        "ordens_servico_pagamento": acesso_financeiro,
        # Compatibilidade com pontos antigos que perguntam se existe alguma
        # operação acessível. As telas usam as capacidades específicas.
        "operacao": producao or acesso_financeiro or gestao,
        "site": criacao,
        "usuarios": superusuario,
        "avaliar_blocos_orcamento": superusuario,
        "avaliar_setores": superusuario,
    }


def pode_excluir_cliente(user) -> bool:
    """Cadastro comercial sem histórico só pode ser apagado por Gestão."""
    return capacidades(user)["excluir_clientes"]


def pode_excluir_orcamento(user, orcamento) -> bool:
    """Limita exclusão a rascunhos e respeita a autoria em Vendas.

    Uma proposta enviada, respondida ou expirada já é histórico comercial.
    Ela pode mudar de situação, mas não deve desaparecer da linha do tempo.
    """
    acesso = capacidades(user)
    if not acesso["excluir_orcamentos"]:
        return False
    if getattr(orcamento, "status", None) != "rascunho":
        return False
    if acesso["excluir_orcamentos_alheios"]:
        return True
    return getattr(orcamento, "responsavel_id", None) == getattr(user, "pk", None)


def limitar_orcamentos(user, queryset):
    """Aplica a carteira individual da função Ambulante no próprio banco."""
    if capacidades(user)["orcamentos_proprios"]:
        return queryset.filter(responsavel=user)
    return queryset


def pode_acessar_orcamento(user, orcamento) -> bool:
    """Confere o objeto, inclusive em POST e prévia por URL direta."""
    acesso = capacidades(user)
    if not acesso["orcamentos"]:
        return False
    if not acesso["orcamentos_proprios"]:
        return True
    return getattr(orcamento, "responsavel_id", None) == getattr(user, "pk", None)


def origem_padrao_orcamento(user) -> str:
    """Origem confiável, derivada da função em vez de um campo do navegador."""
    return "ambulante" if capacidades(user)["orcamentos_proprios"] else "interno"


def atribuir_funcoes(user, codigos) -> list[Funcao]:
    """Substitui somente as funções internas, preservando outros grupos."""
    escolhidas = [
        FUNCOES_POR_CODIGO[codigo]
        for codigo in dict.fromkeys(codigos)
        if codigo in FUNCOES_POR_CODIGO
    ]
    grupos = grupos_de_funcoes()

    user.groups.remove(*Group.objects.filter(name__in=NOMES_DOS_GRUPOS))
    if escolhidas:
        user.groups.add(*(grupos[funcao.grupo] for funcao in escolhidas))
    user._funcoes_interno_cache = frozenset(
        funcao.grupo for funcao in escolhidas
    )

    # is_staff passa a significar "pode usar interfaces de equipe"; o que
    # aparece em cada uma vem das funções acima.
    novo_staff = bool(escolhidas) or user.is_superuser
    if user.is_staff != novo_staff:
        user.is_staff = novo_staff
        user.save(update_fields=["is_staff"])
    return escolhidas
