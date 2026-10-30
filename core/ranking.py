"""Ranking dos jogos do simulador (/jogos/) e a partida grátis do visitante.

Regras que o resto do site pode confiar:

* quem não entrou na conta joga UMA partida de cada jogo. A marca fica na
  sessão (e no aparelho, pelo console); o placar dessa partida fica
  guardado na sessão e entra no ranking quando a pessoa cria a conta ou
  entra -- o login do Django troca a chave da sessão mas mantém os dados;
* cadastrado joga à vontade e guarda o melhor resultado de cada jogo
  (`RecordeJogo`, uma linha por pessoa e jogo);
* RANKING DO JOGO: os recordes daquele jogo, do maior para o menor;
* RANKING GERAL: cada jogo vale até 1.000 pontos de ranking. Quem tem o
  recorde do jogo leva os 1.000, os outros levam a proporção do próprio
  recorde (metade do recorde = 500). Somando todos os jogos, quem joga
  bem tudo sobe -- e os jogos de placar alto (o Hit Music conta em
  centésimos de %) não engolem os de placar baixo (boliche, até 300);
* o ranking aparece com o primeiro nome e a inicial do sobrenome;
* sem a tabela no banco (deploy antes do `migrate`), nada quebra: o
  ranking sai vazio e a partida do cadastrado não é gravada.
"""

from __future__ import annotations

import logging
import time

from django.core.cache import cache
from django.db import DatabaseError, IntegrityError, transaction
from django.db.models import F

from . import arena
from .models import RecordeJogo

log = logging.getLogger(__name__)

#: Teto de sanidade para um placar enviado pelo navegador.
PONTOS_MAXIMOS = 10_000_000
#: Pontos de ranking que cada jogo vale no ranking geral.
PONTOS_POR_JOGO = 1000
#: Intervalo mínimo entre dois envios da mesma sessão (nenhum jogo dura menos).
INTERVALO_MINIMO = 5

SESSAO_JOGADOS = "jogos_jogados"
SESSAO_PENDENTES = "jogos_pendentes"
SESSAO_ULTIMO_ENVIO = "jogos_ultimo_envio"
SESSAO_SALVOS = "jogos_salvos"

CHAVE_CACHE_GERAL = "ranking_jogos:geral"
CHAVE_CACHE_JOGO = "ranking_jogos:jogo:{}"
CACHE_SEGUNDOS = 60
TAMANHO = 10


class PartidaInvalida(ValueError):
    """Jogo que não existe ou placar que não é um número aceitável."""


def _validar(jogo, pontos):
    if jogo not in arena.JOGOS_POR_SLUG:
        raise PartidaInvalida("jogo desconhecido")
    try:
        pontos = int(pontos)
    except (TypeError, ValueError):
        raise PartidaInvalida("placar inválido") from None
    if pontos < 0 or pontos > PONTOS_MAXIMOS:
        raise PartidaInvalida("placar fora do limite")
    return jogo, pontos


def nome_publico(usuario) -> str:
    """Primeiro nome e inicial do sobrenome; nunca o e-mail inteiro."""
    perfil = getattr(usuario, "perfil", None)
    completo = (getattr(perfil, "nome_completo", "") or "").strip() if perfil else ""
    partes = (completo or usuario.get_full_name() or "").split()
    if not partes:
        partes = [(usuario.username or "Jogador").split("@")[0]]
    nome = partes[0][:16].capitalize()
    if len(partes) > 1:
        nome += f" {partes[-1][0].upper()}."
    return nome


# ------------------------------------------------------------------
# Visitante
# ------------------------------------------------------------------

def jogos_jogados(request) -> list[str]:
    """Os jogos que este visitante já usou a partida grátis."""
    return list(request.session.get(SESSAO_JOGADOS, []))


def _marcar_visitante(request, jogo, pontos):
    jogados = set(request.session.get(SESSAO_JOGADOS, []))
    jogados.add(jogo)
    request.session[SESSAO_JOGADOS] = sorted(jogados)
    pendentes = dict(request.session.get(SESSAO_PENDENTES, {}))
    pendentes[jogo] = max(pontos, int(pendentes.get(jogo, 0)))
    request.session[SESSAO_PENDENTES] = pendentes


def adotar_partidas_da_sessao(request, usuario):
    """Ao entrar ou criar a conta, a partida grátis vai para o ranking.

    O que foi salvo fica anotado na sessão: a volta ao simulador mostra
    "resultado salvo no seu nome", com a posição no ranking.
    """
    pendentes = request.session.pop(SESSAO_PENDENTES, None) or {}
    salvos = []
    for jogo, pontos in pendentes.items():
        try:
            jogo, pontos = _validar(jogo, pontos)
        except PartidaInvalida:
            continue
        if pontos and _gravar(usuario, jogo, pontos) is not None:
            salvos.append({"jogo": jogo, "pontos": pontos})
    if salvos:
        request.session[SESSAO_SALVOS] = salvos


def salvos_agora(request) -> list[dict]:
    """Os resultados da partida grátis que acabaram de ir para a conta (uma vez)."""
    salvos = request.session.pop(SESSAO_SALVOS, None) or []
    if not salvos or not request.user.is_authenticated:
        return []
    saida = []
    for item in salvos:
        jogo = arena.JOGOS_POR_SLUG.get(item.get("jogo"))
        if not jogo:
            continue
        lugar = posicao_no_jogo(request.user, jogo["slug"])
        saida.append({
            "jogo": jogo["slug"],
            "titulo": jogo["titulo"],
            "pontos": int(item.get("pontos") or 0),
            "posicao": lugar["posicao"] if lugar else None,
        })
    return saida


# ------------------------------------------------------------------
# Gravação
# ------------------------------------------------------------------

def _gravar(usuario, jogo, pontos, tentativa=0):
    """Soma a partida e guarda o recorde. Devolve o recorde, ou None sem tabela."""
    try:
        with transaction.atomic():
            recorde, criado = RecordeJogo.objects.select_for_update().get_or_create(
                usuario=usuario, jogo=jogo, defaults={"pontos": pontos, "partidas": 1},
            )
            if not criado:
                campos = {"partidas": F("partidas") + 1}
                if pontos > recorde.pontos:
                    campos["pontos"] = pontos
                RecordeJogo.objects.filter(pk=recorde.pk).update(**campos)
                recorde.refresh_from_db()
    except IntegrityError:
        # duas abas terminando juntas: a outra criou a linha primeiro
        return _gravar(usuario, jogo, pontos, tentativa + 1) if tentativa < 1 else None
    except DatabaseError:
        log.exception("Ranking dos jogos: a tabela de recordes não respondeu")
        return None
    cache.delete_many([CHAVE_CACHE_GERAL, CHAVE_CACHE_JOGO.format(jogo)])
    return recorde.pontos


def registrar_partida(request, jogo, pontos) -> dict:
    """O fim de uma partida no simulador. Levanta PartidaInvalida."""
    jogo, pontos = _validar(jogo, pontos)

    agora = time.time()
    envios = dict(request.session.get(SESSAO_ULTIMO_ENVIO, {}))
    muito_cedo = agora - float(envios.get(jogo, 0)) < INTERVALO_MINIMO
    envios[jogo] = agora
    request.session[SESSAO_ULTIMO_ENVIO] = envios

    usuario = request.user
    if not usuario.is_authenticated:
        _marcar_visitante(request, jogo, pontos)
        return {"logado": False, "jogados": jogos_jogados(request)}

    recorde = None if muito_cedo else _gravar(usuario, jogo, pontos)
    return {
        "logado": True,
        "gravado": recorde is not None,
        "recorde": recorde,
        "posicao": posicao_no_jogo(usuario, jogo),
    }


# ------------------------------------------------------------------
# Leitura
# ------------------------------------------------------------------

def _linhas(consulta):
    try:
        return list(consulta)
    except DatabaseError:
        log.exception("Ranking dos jogos: a tabela de recordes não respondeu")
        return []


def ranking_do_jogo(jogo, tamanho=TAMANHO) -> list[dict]:
    chave = CHAVE_CACHE_JOGO.format(jogo)
    lista = cache.get(chave)
    if lista is None:
        recordes = _linhas(
            RecordeJogo.objects.filter(jogo=jogo, pontos__gt=0)
            .select_related("usuario", "usuario__perfil")
            .order_by("-pontos", "atualizado_em")[:tamanho]
        )
        lista = [
            {"posicao": i, "nome": nome_publico(r.usuario), "pontos": r.pontos, "usuario": r.usuario_id}
            for i, r in enumerate(recordes, start=1)
        ]
        cache.set(chave, lista, CACHE_SEGUNDOS)
    return lista


def _tabela_geral() -> list[dict]:
    """Todos os cadastrados que jogaram, já somados e ordenados."""
    tabela = cache.get(CHAVE_CACHE_GERAL)
    if tabela is not None:
        return tabela
    linhas = _linhas(
        RecordeJogo.objects.filter(pontos__gt=0, jogo__in=list(arena.JOGOS_POR_SLUG))
        .values_list("usuario_id", "jogo", "pontos")
    )
    maior = {}
    for _, jogo, pontos in linhas:
        maior[jogo] = max(maior.get(jogo, 0), pontos)
    soma = {}
    jogos = {}
    for usuario_id, jogo, pontos in linhas:
        soma[usuario_id] = soma.get(usuario_id, 0) + round(PONTOS_POR_JOGO * pontos / maior[jogo])
        jogos[usuario_id] = jogos.get(usuario_id, 0) + 1
    ordem = sorted(soma, key=lambda u: (-soma[u], -jogos[u], u))
    nomes = {}
    if ordem:
        from django.contrib.auth.models import User

        for usuario in _linhas(User.objects.filter(pk__in=ordem[:TAMANHO]).select_related("perfil")):
            nomes[usuario.pk] = nome_publico(usuario)
    tabela = [
        {"posicao": i, "usuario": u, "nome": nomes.get(u, ""), "pontos": soma[u], "jogos": jogos[u]}
        for i, u in enumerate(ordem, start=1)
    ]
    cache.set(CHAVE_CACHE_GERAL, tabela, CACHE_SEGUNDOS)
    return tabela


def ranking_geral(tamanho=TAMANHO) -> list[dict]:
    return _tabela_geral()[:tamanho]


def posicao_no_jogo(usuario, jogo):
    try:
        recorde = RecordeJogo.objects.filter(usuario=usuario, jogo=jogo).values_list("pontos", flat=True).first()
        if not recorde:
            return None
        acima = RecordeJogo.objects.filter(jogo=jogo, pontos__gt=recorde).count()
    except DatabaseError:
        return None
    return {"posicao": acima + 1, "pontos": recorde}


def posicao_geral(usuario):
    for linha in _tabela_geral():
        if linha["usuario"] == usuario.pk:
            return {"posicao": linha["posicao"], "pontos": linha["pontos"]}
    return None


def _publico(lista):
    """Sem o id de usuário na resposta pública."""
    return [{k: v for k, v in linha.items() if k != "usuario"} for linha in lista]


def painel(request, jogo) -> dict:
    """Tudo o que a ficha do simulador mostra: os dois rankings e a pessoa."""
    usuario = request.user
    logado = usuario.is_authenticated
    dados = {
        "jogo": jogo,
        "rankingJogo": _publico(ranking_do_jogo(jogo)),
        "rankingGeral": _publico(ranking_geral()),
        "logado": logado,
        "jogados": [] if logado else jogos_jogados(request),
        "eu": None,
    }
    if logado:
        dados["eu"] = {
            "nome": nome_publico(usuario),
            "jogo": posicao_no_jogo(usuario, jogo),
            "geral": posicao_geral(usuario),
        }
    return dados
