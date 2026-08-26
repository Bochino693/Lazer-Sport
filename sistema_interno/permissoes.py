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
        "Clientes, orçamentos, pedidos e acompanhamento comercial.",
        "bi-file-earmark-text",
    ),
    Funcao(
        "gestao",
        GESTAO,
        "Gestão",
        "Financeiro, indicadores, clientes, orçamentos e operação comercial.",
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
    gestao = tem_funcao(user, GESTAO)

    return {
        "superusuario": superusuario,
        "producao": producao,
        "criacao": criacao,
        "vendas": vendas,
        "gestao": gestao,
        "estoque": producao or gestao,
        "clientes": vendas or gestao,
        "orcamentos": vendas or gestao,
        "financeiro": gestao,
        "operacao": producao or vendas or gestao,
        "site": criacao,
        "usuarios": superusuario,
    }


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
