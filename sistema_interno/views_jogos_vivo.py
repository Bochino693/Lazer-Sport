"""AO VIVO NO PORTAL (/site/jogos/ao-vivo/): o que está acontecendo agora no Lazer & Sport Games.

Para quem cuida dos jogos ver, sem abrir o portal, se tem gente jogando e se o portal está
trazendo cadastro:

* gente ONLINE agora e quem está JOGANDO o quê (core/presenca_jogos.py: a batida de cada aba
  do portal, na memória do site -- por isso o número zera quando o site é publicado de novo);
* as PARTIDAS contadas de cada jogo (o "Mais jogados" do portal, PartidasDoJogo);
* quem jogou HOJE com conta, o RANKING geral e o campeão de cada jogo da casa;
* as CONTAS NOVAS (hoje e nos últimos 7 dias): o convite das 2 jogadas grátis existe para isto.

A tela atualiza sozinha a cada 15 s pelo mesmo endereço com ``?formato=json``.
Só o superadministrador, como a tela dos jogos.
"""

from __future__ import annotations

import datetime as dt
import logging

from django.contrib.auth.models import User
from django.db import DatabaseError
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views import View

from core import arena, portal_jogos, presenca_jogos, ranking as ranking_dos_jogos
from core.models import JogoCadastrado
from core.objetos_3d import tabela_pronta

from .views import SuperusuarioInternoRequiredMixin

log = logging.getLogger(__name__)

#: De quanto em quanto tempo a tela pede os números de novo (a batida das abas é a cada 30 s).
ATUALIZA_SEGUNDOS = 15


def _nomes_dos_jogos():
    """slug -> (nome, cor, se é da casa): os da casa e os cadastrados pelo painel."""
    nomes = {j["slug"]: (j["titulo"], j.get("cor") or "#3fd0ff", True) for j in arena.JOGOS}
    if tabela_pronta(JogoCadastrado):
        try:
            for slug, nome, cor in JogoCadastrado.objects.values_list("slug", "nome", "cor"):
                nomes.setdefault(slug, (nome, cor or "#ff3df2", False))
        except DatabaseError:
            log.warning("Ao vivo: não deu para ler os jogos cadastrados")
    return nomes


def _contas_novas():
    hoje = timezone.make_aware(dt.datetime.combine(timezone.localdate(), dt.time.min))
    try:
        return {
            "hoje": User.objects.filter(date_joined__gte=hoje).count(),
            "semana": User.objects.filter(date_joined__gte=hoje - dt.timedelta(days=6)).count(),
        }
    except DatabaseError:
        return {"hoje": 0, "semana": 0}


def painel_ao_vivo():
    """Os números da tela, prontos para o template e para o JSON."""
    nomes = _nomes_dos_jogos()

    def jogo(slug, n):
        nome, cor, casa = nomes.get(slug, (slug, "#3fd0ff", False))
        return {"slug": slug, "nome": nome, "cor": cor, "casa": casa, "n": n}

    agora = presenca_jogos.resumo()
    jogando = sorted((jogo(s, n) for s, n in agora["jogando"].items() if n > 0), key=lambda j: (-j["n"], j["nome"]))
    vivo = portal_jogos.contagens()
    partidas = vivo.get("partidas") or {}
    mais_jogados = sorted((jogo(s, n) for s, n in partidas.items() if n > 0 and s in nomes), key=lambda j: (-j["n"], j["nome"]))[:10]
    # o ranking direto do core.ranking (o portal_jogos monta os links do portal, que este
    # endereço -- o do painel -- não conhece)
    try:
        geral = ranking_dos_jogos.ranking_geral(10)
        campeoes = []
        for j in arena.JOGOS:
            primeiro = ranking_dos_jogos.ranking_do_jogo(j["slug"], 1)
            if primeiro:
                campeoes.append({"jogo": j["titulo"], "cor": j.get("cor") or "#3fd0ff", **primeiro[0]})
    except DatabaseError:
        geral, campeoes = [], []
    return {
        "online": agora["online"],
        "jogando_total": sum(j["n"] for j in jogando),
        "jogando": jogando,
        "partidas_total": sum(n for s, n in partidas.items() if s in nomes),
        "mais_jogados": mais_jogados,
        "maior_partidas": mais_jogados[0]["n"] if mais_jogados else 0,
        "jogadores_hoje": vivo.get("jogadores_hoje", 0),
        "contas": _contas_novas(),
        # sem o id de quem joga: só o nome público (primeiro nome e inicial)
        "ranking": [{"posicao": r["posicao"], "nome": r["nome"], "pontos": r["pontos"], "jogos": r.get("jogos", 0)}
                    for r in geral],
        "campeoes": [{"jogo": c["jogo"], "cor": c["cor"], "nome": c["nome"], "pontos": c["pontos"]} for c in campeoes],
        "hora": timezone.localtime().strftime("%H:%M:%S"),
    }


class JogosAoVivoView(SuperusuarioInternoRequiredMixin, View):
    rota_padrao = "jogos_ao_vivo"
    template_name = "jogos_ao_vivo_inner.html"

    def get(self, request):
        dados = painel_ao_vivo()
        if request.GET.get("formato") == "json":
            resposta = JsonResponse(dados)
            resposta["Cache-Control"] = "no-store"
            return resposta
        return render(request, self.template_name, {"vivo": dados, "atualiza": ATUALIZA_SEGUNDOS})
