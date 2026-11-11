"""AS JOGADAS: cada Jogar de verdade, com data, quem e por onde.

POR QUE EXISTE. O "Mais jogados" do portal (`PartidasDoJogo`) guarda só um
total por jogo, contado no máximo uma vez a cada 30 min por visitante; e "quem
jogou hoje" saía só da tabela de recordes, que só os jogos da casa (com
pontuação) tocam. Resultado: quem jogava um jogo de console com a conta aberta
(o Super Mario 64, por exemplo) não aparecia em lugar nenhum, e o emulador nem
avisava o site quando a pessoa tinha conta. Agora:

  * toda entrada de jogo avisa o site (/jogos/abriu/): a página do jogo, o
    emulador (inclusive com conta), o app do portal e os jogos da casa;
  * cada aviso vira uma `JogadaRegistrada` (o jogo, a conta ou um número da
    sessão do visitante, se é da equipe, a origem e a hora);
  * a mesma pessoa no mesmo jogo dentro de `REPETIDA_SEGUNDOS` é a mesma
    jogada (o Jogar da página e o do emulador em seguida; o recarregar);
  * a equipe conta, marcada: o painel mostra com ou sem ela.

Nada disso trava o jogo: erro de banco só vai para o log.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import logging
import time

from django.db import DatabaseError
from django.db.models import Count, Q
from django.utils import timezone

log = logging.getLogger(__name__)

#: A mesma pessoa no mesmo jogo dentro deste tempo é a mesma jogada.
REPETIDA_SEGUNDOS = 3 * 60
#: Onde a sessão guarda a hora da última jogada registrada de cada jogo.
SESSAO = "jogos_jogadas_registradas"
ORIGENS = {"pagina", "emulador", "app", "casa", "html"}


def _visitante(request) -> str:
    """Um número curto tirado da sessão: conta pessoas sem dizer quem são."""
    try:
        if not request.session.session_key:
            request.session.save()
        chave = request.session.session_key or ""
    except Exception:  # noqa: BLE001 -- sem sessão, conta sem o número
        chave = ""
    return hashlib.sha1(chave.encode()).hexdigest()[:16] if chave else ""


def registrar(request, slug: str, origem: str = "") -> bool:
    """Anota a jogada (devolve se anotou: a repetida em seguida não conta)."""
    from .models import JogadaRegistrada
    from .objetos_3d import tabela_pronta

    agora = time.time()
    feitas = dict(request.session.get(SESSAO, {}))
    if agora - float(feitas.get(slug, 0)) < REPETIDA_SEGUNDOS:
        return False
    # só as últimas 50 (a sessão não cresce sem fim)
    feitas[slug] = agora
    if len(feitas) > 50:
        feitas = dict(sorted(feitas.items(), key=lambda par: par[1])[-50:])
    request.session[SESSAO] = feitas
    if not tabela_pronta(JogadaRegistrada):
        return False
    usuario = request.user if request.user.is_authenticated else None
    try:
        JogadaRegistrada.objects.create(
            jogo=slug[:80],
            usuario=usuario,
            equipe=bool(usuario and usuario.is_staff),
            visitante="" if usuario else _visitante(request),
            origem=origem if origem in ORIGENS else "",
        )
    except DatabaseError:
        log.warning("Jogadas: não deu para anotar a jogada de %s", slug)
        return False
    return True


# ------------------------------------------------------------------ as contas do painel

PERIODOS = {
    "hoje": ("Hoje", 0),
    "semana": ("7 dias", 6),
    "mes": ("30 dias", 29),
    "trimestre": ("3 meses", 89),
    "semestre": ("Semestre", 179),
    "ano": ("Ano", 364),
}


def inicio_do_periodo(periodo: str, hoje: dt.date | None = None) -> dt.datetime:
    """A meia-noite (no fuso do site) do primeiro dia do período."""
    hoje = hoje or timezone.localdate()
    dias = PERIODOS.get(periodo, PERIODOS["semana"])[1]
    return timezone.make_aware(dt.datetime.combine(hoje - dt.timedelta(days=dias), dt.time.min))


def resumo(periodo: str = "hoje", com_equipe: bool = True, hoje: dt.date | None = None) -> dict:
    """Jogadas, pessoas (com conta e sem) e os jogos mais jogados do período."""
    from .models import JogadaRegistrada
    from .objetos_3d import tabela_pronta

    vazio = {"jogadas": 0, "com_conta": 0, "visitantes": 0, "equipe": 0, "por_jogo": {}, "quem": []}
    if not tabela_pronta(JogadaRegistrada):
        return vazio
    filtro = Q(quando__gte=inicio_do_periodo(periodo, hoje))
    if not com_equipe:
        filtro &= Q(equipe=False)
    try:
        base = JogadaRegistrada.objects.filter(filtro)
        totais = base.aggregate(
            jogadas=Count("id"),
            com_conta=Count("usuario", distinct=True),
            visitantes=Count("visitante", distinct=True, filter=Q(usuario__isnull=True) & ~Q(visitante="")),
            equipe=Count("usuario", distinct=True, filter=Q(equipe=True)),
        )
        por_jogo = dict(base.values_list("jogo").annotate(n=Count("id")).values_list("jogo", "n"))
        quem = list(
            base.filter(usuario__isnull=False)
            .values("usuario_id", "usuario__first_name", "usuario__username", "equipe")
            .annotate(jogadas=Count("id"))
            .order_by("-jogadas")[:20]
        )
    except DatabaseError:
        log.warning("Jogadas: não deu para montar o resumo de %s", periodo)
        return vazio
    return {
        **{chave: totais.get(chave) or 0 for chave in ("jogadas", "com_conta", "visitantes", "equipe")},
        "por_jogo": por_jogo,
        "quem": [
            {
                "nome": (q["usuario__first_name"] or q["usuario__username"] or "").strip()[:40],
                "equipe": q["equipe"],
                "jogadas": q["jogadas"],
            }
            for q in quem
        ],
    }


def jogadores_hoje(com_equipe: bool = True) -> int:
    """Quantas pessoas com conta jogaram hoje (qualquer jogo, inclusive os de console)."""
    return resumo("hoje", com_equipe=com_equipe)["com_conta"]
