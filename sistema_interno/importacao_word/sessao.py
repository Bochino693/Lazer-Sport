"""Onde a leitura espera a conferência: na sessão de quem importou.

POR QUE NA SESSÃO, E NÃO NUMA TABELA. A leitura é rascunho de rascunho:
serve para a tela de conferência e mais nada, e só a pessoa que importou
precisa dela. Uma tabela guardaria texto de documento de cliente para
sempre, e alguém teria de lembrar de limpar. Na sessão ela some quando o
orçamento é criado, quando a pessoa descarta, quando passa do prazo
abaixo -- ou quando a sessão acaba.

O ARQUIVO NUNCA ENTRA AQUI: só as linhas de texto numeradas e a leitura.
Recarregar a conferência não chama a IA de novo (custaria tempo e
dinheiro, e poderia ler diferente).
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta

from django.utils import timezone

CHAVE = "importacoes_orcamento_word"
#: Uma conferência aberta de manhã ainda vale à tarde; no dia seguinte, não.
VALIDADE = timedelta(hours=12)
#: Três importações em conferência ao mesmo tempo é o bastante; a quarta
#: empurra a mais velha para fora (a sessão não é depósito).
MAXIMO = 3


def _todas(request) -> dict:
    guardadas = request.session.get(CHAVE) or {}
    agora = timezone.now()
    vivas = {}
    for token, leitura in guardadas.items():
        try:
            criada = datetime.fromisoformat(leitura.get("criado_em", ""))
        except ValueError:
            continue
        if agora - criada <= VALIDADE:
            vivas[token] = leitura
    return vivas


def guardar(request, leitura: dict) -> str:
    token = secrets.token_urlsafe(12)
    todas = _todas(request)
    leitura = dict(leitura, criado_em=timezone.now().isoformat(), autor=request.user.pk)
    todas[token] = leitura
    if len(todas) > MAXIMO:
        for velha in sorted(todas, key=lambda t: todas[t]["criado_em"])[: len(todas) - MAXIMO]:
            todas.pop(velha)
    request.session[CHAVE] = todas
    request.session.modified = True
    return token


def abrir(request, token: str) -> dict | None:
    leitura = _todas(request).get(token)
    if not leitura or leitura.get("autor") != request.user.pk:
        return None
    return leitura


def atualizar(request, token: str, **mudancas):
    todas = _todas(request)
    if token in todas:
        todas[token].update(mudancas)
        request.session[CHAVE] = todas
        request.session.modified = True


def descartar(request, token: str):
    todas = _todas(request)
    todas.pop(token, None)
    request.session[CHAVE] = todas
    request.session.modified = True


# ----------------------------------------------------------------------
# O resumo da tela de conclusão
# ----------------------------------------------------------------------
#: O que a tela "Pronto" precisa saber e o banco não guarda: se o cliente
#: nasceu agora ou já existia, e o que foi completado nele. Fica até a
#: sessão acabar; as cinco últimas bastam (recarregar a tela não perde).
CHAVE_CONCLUSAO = "importacoes_orcamento_concluidas"
MAXIMO_CONCLUSOES = 5


def guardar_conclusao(request, pk: int, resumo: dict):
    concluidas = dict(request.session.get(CHAVE_CONCLUSAO) or {})
    concluidas[str(pk)] = dict(resumo, autor=request.user.pk)
    for velha in list(concluidas)[: max(0, len(concluidas) - MAXIMO_CONCLUSOES)]:
        concluidas.pop(velha)
    request.session[CHAVE_CONCLUSAO] = concluidas
    request.session.modified = True


def conclusao(request, pk: int) -> dict | None:
    resumo = (request.session.get(CHAVE_CONCLUSAO) or {}).get(str(pk))
    if not resumo or resumo.get("autor") != request.user.pk:
        return None
    return resumo
