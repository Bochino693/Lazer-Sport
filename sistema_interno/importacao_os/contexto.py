"""O que toda leitura precisa saber e quase nunca muda: guardado por um minuto.

POR QUE GUARDAR. Cada documento é um pedido (o navegador manda um por vez),
e cada leitura precisa de quem é a Lazer & Sport (CNPJ, telefones, endereço
da fábrica), de quem é da equipe (para nunca virar cliente), de quem pode
ser o técnico, e às vezes do catálogo. Com o banco a ~170 ms de distância,
são quatro a sete viagens por documento -- num lote de dez, mais de dez
segundos só nisso. Guardado no cache do processo por um minuto, o lote
inteiro paga uma vez.

Um minuto é o atraso aceitável: quem entrou na equipe agora é reconhecido
como "da casa" no documento lido daqui a sessenta segundos.
"""

from __future__ import annotations

from django.core.cache import cache

CHAVE = "importacao_os:contexto:v1"
CHAVE_CATALOGO = "importacao_os:catalogo:v1"
VALIDADE = 60


def _tecnicos() -> list[dict]:
    """Quem a tela da O.S. oferece como técnico: Produção, Gestão e o super."""
    from django.contrib.auth.models import User
    from django.db.models import Q

    from ..permissoes import GESTAO, PRODUCAO

    linhas = (
        User.objects.filter(is_active=True)
        .filter(Q(is_superuser=True) | Q(groups__name__in=(PRODUCAO, GESTAO)))
        .distinct()
        .values_list("id", "first_name", "last_name", "username")
    )
    return [
        {"id": pk, "nome": f"{primeiro} {ultimo}".strip() or usuario, "usuario": usuario,
         "primeiro": primeiro, "ultimo": ultimo}
        for pk, primeiro, ultimo, usuario in linhas
    ]


def carregar() -> dict:
    dados = cache.get(CHAVE)
    if dados is None:
        from ..importacao_word import conferencia, identificar

        dados = {
            "empresa": conferencia.identidade_da_empresa(),
            "internos": identificar.pessoas_internas(),
            "tecnicos": _tecnicos(),
        }
        cache.set(CHAVE, dados, VALIDADE)
    return dados


def catalogo() -> list[dict]:
    """Brinquedos, produtos e peças (o mesmo catálogo da busca do orçamento)."""
    dados = cache.get(CHAVE_CATALOGO)
    if dados is None:
        from ..importacao_word import catalogo as cat

        dados = cat.carregar_catalogo()
        cache.set(CHAVE_CATALOGO, dados, VALIDADE)
    return dados


def esquecer():
    cache.delete_many([CHAVE, CHAVE_CATALOGO])
