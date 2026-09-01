"""O que toda página do painel recebe sem pedir.

Antes este arquivo contava vendas, pedidos, manutenções e produção com
regras escritas aqui dentro, e a home recontava estoque crítico com outra
regra. Agora quem sabe o que é pendência é `avisos.py`, e aqui só se
traduz aquilo para o que os templates usam.

Os `count_*` continuam existindo porque as bolinhas do menu lateral são
montadas com eles em base_inner.html — e o painel /adm também usa
count_manutencao. São derivados dos MESMOS avisos, e não de consultas
próprias: enquanto forem a mesma conta, o número na bolinha e o número na
central não podem divergir.

POR QUE TUDO É PREGUIÇOSO. Este é um context processor global: roda em
toda página do site, não só no painel. A versão antiga disparava quatro
COUNT para qualquer usuário da equipe navegando na loja, e a central de
avisos precisa de mais. Embrulhado em SimpleLazyObject, nada é consultado
enquanto o template não pedir o valor — e a loja nunca pede. O cálculo em
si acontece uma vez só por requisição, por mais chaves que sejam lidas.
"""

from django.conf import settings
from django.core.cache import cache
from django.utils.functional import SimpleLazyObject

from .avisos import coletar
from .permissoes import capacidades, faz_parte_da_equipe

#: Estado de quem não é da equipe. O template nunca encontra variável
#: faltando, e nenhuma consulta é feita para chegar aqui.
VAZIO = {
    "avisos": [],
    "avisos_urgentes": 0,
    "total_avisos": 0,
    "count_vendas": 0,
    "count_pedidos": 0,
    "count_manutencao": 0,
    "count_producao": 0,
    "count_orcamentos": 0,
    "count_ordens_servico": 0,
    "count_clientes_incompletos": 0,
    "eh_gestor_interno": False,
    "permissoes_interno": {},
}


def _apurar(usuario):
    """Roda as consultas e monta tudo que os templates podem pedir."""
    avisos = coletar(usuario)
    por_chave = {aviso.chave: aviso.quantidade for aviso in avisos}
    orcamentos_notificados = frozenset().union(*(
        aviso.orcamentos for aviso in avisos if aviso.orcamentos
    ))
    sem_orcamento = [aviso for aviso in avisos if not aviso.orcamentos]
    orcamentos_urgentes = frozenset().union(*(
        aviso.orcamentos
        for aviso in avisos
        if aviso.orcamentos and aviso.urgente
    ))

    return {
        "avisos": avisos,
        # Uma negociação conta uma vez. Validade, resposta, atividade e
        # versões continuam explicadas em linhas separadas na central, mas
        # não podem fazer a mesma proposta ocupar duas bolinhas no sino.
        "avisos_urgentes": (
            len(orcamentos_urgentes)
            + sum(a.quantidade for a in sem_orcamento if a.urgente)
        ),
        "total_avisos": (
            len(orcamentos_notificados)
            + sum(a.quantidade for a in sem_orcamento)
        ),

        # As bolinhas do menu. Zero quando não há aviso daquela chave —
        # que é o mesmo que dizer "nada pendente aqui".
        "count_vendas": por_chave.get("vendas", 0),
        "count_pedidos": por_chave.get("pedidos", 0),
        "count_manutencao": por_chave.get("manutencoes", 0),
        "count_producao": por_chave.get("producao", 0),
        "count_orcamentos": len(orcamentos_notificados),
        "count_ordens_servico": por_chave.get("ordens_servico", 0),
        "count_clientes_incompletos": por_chave.get("clientes_incompletos", 0),
    }


def _apurar_com_cache(usuario, versao_atividade=None):
    """Reaproveita os contadores durante a troca rápida entre telas.

    A central custa vários COUNT no banco remoto e antes repetia todos em
    cada clique do menu. Um intervalo curto mantém o aviso operacional vivo,
    mas faz uma sequência Clientes → Orçamentos → Produção pagar a conta uma
    vez só.
    """
    try:
        ttl = max(5, int(getattr(settings, "INTERNO_AVISOS_CACHE_TTL", 20)))
    except (TypeError, ValueError):
        ttl = 20

    chave = _chave_avisos(usuario, versao_atividade)
    apurado = cache.get(chave)
    if apurado is None:
        apurado = _apurar(usuario)
        cache.set(chave, apurado, ttl)
    return apurado


def invalidar_avisos(usuario, versao_atividade=None):
    """Faz qualquer variante do cache refletir uma ação operacional.

    A geração entra em todas as chaves do usuário. Só apagar a chave base
    deixava viva a variante usada pelo endpoint em tempo real.
    """
    if getattr(usuario, "pk", None):
        chave = _chave_geracao(usuario)
        try:
            cache.incr(chave)
        except ValueError:
            cache.set(chave, 1, None)


def _chave_avisos(usuario, versao_atividade=None):
    # O instante de criação diferencia uma conta real de outra que reutilize
    # o mesmo id após limpeza/importação do banco — e também impede que o
    # cache local sobreviva entre casos isolados da suíte de testes.
    criado = getattr(usuario, "date_joined", None)
    versao = int(criado.timestamp() * 1_000_000) if criado else 0
    atividade = f":a{int(versao_atividade)}" if versao_atividade is not None else ""
    geracao = cache.get(_chave_geracao(usuario), 0) or 0
    return f"interno:avisos:v4:{usuario.pk}:{versao}:g{geracao}{atividade}"


def _chave_geracao(usuario):
    return f"interno:avisos:geracao:{usuario.pk}"


def fab_counts(request):
    """Avisos do painel + as contagens que os menus usam."""
    usuario = getattr(request, "user", None)

    if usuario is None or not usuario.is_authenticated:
        return dict(VAZIO)

    if not faz_parte_da_equipe(usuario):
        return dict(VAZIO)

    acesso = capacidades(usuario)

    # Um único cálculo compartilhado por todas as chaves: o SimpleLazyObject
    # de fora memoriza o resultado, e os de dentro apenas leem dele.
    apurado = SimpleLazyObject(lambda: _apurar_com_cache(usuario))

    def campo(chave):
        return SimpleLazyObject(lambda: apurado[chave])

    contexto = {
        chave: campo(chave)
        for chave in (
            "avisos",
            "avisos_urgentes",
            "total_avisos",
            "count_vendas",
            "count_pedidos",
            "count_manutencao",
            "count_producao",
            "count_orcamentos",
            "count_ordens_servico",
            "count_clientes_incompletos",
        )
    }
    contexto["eh_gestor_interno"] = acesso["gestao"]
    contexto["permissoes_interno"] = acesso
    return contexto
