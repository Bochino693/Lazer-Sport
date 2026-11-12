"""Quem está online agora e quando cada conta foi vista por último.

O QUE JÁ EXISTIA, E POR QUE NÃO SERVIA.
  * `User.last_login` só muda quando a pessoa digita a senha. Quem fica
    logado por semanas (o celular do cliente, o tablet do galpão) aparece
    como "entrou há 20 dias" estando com o site aberto agora.
  * A presença dos jogos (core/presenca_jogos.py) conta APARELHOS, sem
    conta nem nome, na memória do processo -- de propósito: diz "12 pessoas
    jogando", nunca quem.
  * As sessões guardam a validade, não o último uso.

O QUE ISTO FAZ. Toda requisição de uma conta logada (site, painel ou
aplicativo) é um sinal de vida. O `PresencaMiddleware` anota o sinal em
`PresencaUsuario` (o último) e em `AcessoDiario` (um por dia, para os
gráficos de ativos) -- mas NO MÁXIMO UMA VEZ POR MINUTO POR CONTA: o
primeiro sinal do minuto marca uma chave no cache e os seguintes morrem
ali, sem banco. A gravação vai pela mesma linha de fundo dos cliques
(core/cliques.py): a página não espera por ela.

"Online" é ter dado sinal nos últimos ONLINE_MINUTOS. O painel mostra o
resto como "Visto há 2 h", "Visto ontem às 14:32", "Nunca entrou".

Desligável por PRESENCA_DE_USUARIOS (desligado nos testes que não são
dele: uma gravação a mais mudaria a conta de consultas de toda a suíte).
"""

from __future__ import annotations

import datetime as dt
import logging

from django.conf import settings
from django.core.cache import cache
from django.db import DatabaseError, IntegrityError, transaction
from django.utils import timezone

log = logging.getLogger("core.presenca")

#: Sinal mais novo que isto = online agora.
ONLINE_MINUTOS = 5
#: No máximo uma gravação por conta a cada tantos segundos.
INTERVALO_GRAVACAO = 60
PREFIXO_CACHE = "ls:presenca:"


def ligada():
    return bool(getattr(settings, "PRESENCA_DE_USUARIOS", True))


def onde_foi_visto(request):
    if getattr(request, "is_interno", False):
        return "painel"
    if (request.path or "").startswith("/api/"):
        return "app"
    return "site"


def marcar(usuario_id, onde="site", agora=None):
    """Anota o sinal de vida; devolve True quando este sinal vai ao banco.

    `cache.add` só grava se a chave não existe: é o freio. Num minuto com
    trinta requisições da mesma conta, só a primeira passa daqui.
    """
    if not usuario_id:
        return False
    if not cache.add(f"{PREFIXO_CACHE}{usuario_id}", 1, INTERVALO_GRAVACAO):
        return False
    from . import cliques

    cliques.depois(gravar, usuario_id, onde, agora or timezone.now())
    return True


def gravar(usuario_id, onde, agora):
    """O último sinal e o dia de acesso. Nunca levanta (presença não derruba página)."""
    from .models import AcessoDiario, PresencaUsuario

    try:
        with transaction.atomic():
            if not PresencaUsuario.objects.filter(usuario_id=usuario_id).update(visto_em=agora, onde=onde):
                PresencaUsuario.objects.create(usuario_id=usuario_id, visto_em=agora, onde=onde)
    except IntegrityError:
        # a conta foi apagada no meio do caminho, ou outro processo criou a linha
        pass
    except DatabaseError:
        log.warning("presenca: o sinal da conta %s não foi gravado", usuario_id, exc_info=True)
        return

    dia = timezone.localtime(agora).date()
    try:
        with transaction.atomic():
            if not AcessoDiario.objects.filter(usuario_id=usuario_id, dia=dia).update(ultimo=agora):
                AcessoDiario.objects.create(usuario_id=usuario_id, dia=dia, primeiro=agora, ultimo=agora)
    except IntegrityError:
        pass
    except DatabaseError:
        log.warning("presenca: o acesso do dia da conta %s não foi gravado", usuario_id, exc_info=True)


class PresencaMiddleware:
    """Depois da resposta: a conta logada deu sinal de vida.

    Fica depois do AuthenticationMiddleware. Lê `request.user` só quando a
    sessão já o carregou ou quando há cookie de sessão: o visitante anônimo
    da vitrine em cache não ganha consulta nenhuma por causa disto.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        resposta = self.get_response(request)
        if not ligada():
            return resposta
        try:
            if not (
                settings.SESSION_COOKIE_NAME in request.COOKIES
                or request.META.get("HTTP_AUTHORIZATION")
                or hasattr(request, "_cached_user")
            ):
                return resposta  # anônimo sem sessão: nada a anotar, nenhuma consulta
            usuario = getattr(request, "user", None)
            if usuario is not None and getattr(usuario, "is_authenticated", False):
                marcar(usuario.pk, onde_foi_visto(request))
        except Exception:  # noqa: BLE001 -- sinal de vida nunca derruba a resposta
            log.warning("presenca: falhou ao anotar o sinal", exc_info=True)
        return resposta


# ----------------------------------------------------------------------
# Como o painel conta isso para as pessoas
# ----------------------------------------------------------------------

def _hora(valor):
    return timezone.localtime(valor).strftime("%H:%M")


def situacao(visto_em=None, last_login=None, agora=None):
    """{"online", "codigo", "texto", "quando"} para o selo da lista e o modal.

    `visto_em` é o sinal de vida (presença); `last_login` é o reserva para
    as contas que não aparecem desde que a presença passou a existir.
    """
    agora = agora or timezone.now()
    if visto_em and agora - visto_em <= dt.timedelta(minutes=ONLINE_MINUTOS):
        return {"online": True, "codigo": "online", "texto": "Online agora", "quando": visto_em.isoformat()}

    ultimo = max([v for v in (visto_em, last_login) if v], default=None)
    if ultimo is None:
        return {"online": False, "codigo": "nunca", "texto": "Nunca entrou", "quando": None}

    verbo = "Visto" if visto_em and ultimo == visto_em else "Entrou"
    local = timezone.localtime(ultimo)
    hoje = timezone.localtime(agora).date()
    passado = agora - ultimo
    if passado < dt.timedelta(hours=1):
        minutos = max(1, int(passado.total_seconds() // 60))
        texto = f"{verbo} há {minutos} min"
    elif local.date() == hoje:
        horas = int(passado.total_seconds() // 3600)
        texto = f"{verbo} há {horas} h"
    elif local.date() == hoje - dt.timedelta(days=1):
        texto = f"{verbo} ontem às {_hora(ultimo)}"
    elif local.year == hoje.year:
        texto = f"{verbo} em {local:%d/%m} às {_hora(ultimo)}"
    else:
        texto = f"{verbo} em {local:%d/%m/%Y}"
    codigo = "recente" if passado <= dt.timedelta(days=7) else "antigo"
    return {"online": False, "codigo": codigo, "texto": texto, "quando": ultimo.isoformat()}


def situacao_da_conta(usuario, agora=None):
    """A situação de um `User` (com `presenca` já carregada por select_related)."""
    try:
        presenca = usuario.presenca
    except Exception:  # noqa: BLE001 -- RelatedObjectDoesNotExist: nunca deu sinal
        presenca = None
    return situacao(getattr(presenca, "visto_em", None), usuario.last_login, agora)


def resumo(agora=None):
    """Os números do topo da tela Usuários, numa consulta só."""
    from django.contrib.auth.models import User
    from django.db.models import Count, Q

    agora = agora or timezone.now()
    local = timezone.localtime(agora)
    meia_noite = local.replace(hour=0, minute=0, second=0, microsecond=0)

    def desde(momento):
        return Q(presenca__visto_em__gte=momento) | Q(last_login__gte=momento)

    numeros = User.objects.aggregate(
        online=Count("pk", filter=Q(presenca__visto_em__gte=agora - dt.timedelta(minutes=ONLINE_MINUTOS))),
        hoje=Count("pk", filter=desde(meia_noite)),
        semana=Count("pk", filter=desde(meia_noite - dt.timedelta(days=6))),
        mes=Count("pk", filter=desde(meia_noite - dt.timedelta(days=29))),
        nunca=Count("pk", filter=Q(last_login__isnull=True, presenca__isnull=True)),
    )
    return numeros
