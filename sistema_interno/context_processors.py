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

from django.utils.functional import SimpleLazyObject

from .avisos import coletar, eh_gestor

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
    "eh_gestor_interno": False,
}


def _apurar(usuario):
    """Roda as consultas e monta tudo que os templates podem pedir."""
    avisos = coletar(usuario)
    por_chave = {aviso.chave: aviso.quantidade for aviso in avisos}

    return {
        "avisos": avisos,
        "avisos_urgentes": sum(1 for a in avisos if a.urgente),
        "total_avisos": len(avisos),

        # As bolinhas do menu. Zero quando não há aviso daquela chave —
        # que é o mesmo que dizer "nada pendente aqui".
        "count_vendas": por_chave.get("vendas", 0),
        "count_pedidos": por_chave.get("pedidos", 0),
        "count_manutencao": por_chave.get("manutencoes", 0),
        "count_producao": por_chave.get("producao", 0),
        "count_orcamentos": (
            por_chave.get("orcamentos_vencidos", 0)
            + por_chave.get("orcamentos_vencendo", 0)
            + por_chave.get("orcamentos_aprovados", 0)
        ),
    }


def fab_counts(request):
    """Avisos do painel + as contagens que os menus usam."""
    usuario = getattr(request, "user", None)

    if usuario is None or not usuario.is_authenticated:
        return dict(VAZIO)

    # eh_gestor não vai ao banco no caso comum (superusuário sai no
    # primeiro if; os demais custam um acesso ao perfil de gerente, que o
    # próprio menu já precisa para decidir o que mostrar).
    gestor = eh_gestor(usuario)

    if not (usuario.is_staff or gestor):
        return dict(VAZIO)

    # Um único cálculo compartilhado por todas as chaves: o SimpleLazyObject
    # de fora memoriza o resultado, e os de dentro apenas leem dele.
    apurado = SimpleLazyObject(lambda: _apurar(usuario))

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
        )
    }
    contexto["eh_gestor_interno"] = gestor
    return contexto
