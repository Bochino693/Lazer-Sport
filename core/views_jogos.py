"""O simulador: a área dedicada às prévias dos jogos das máquinas.

Cada jogo tem o seu endereço (/jogos/<jogo>/) -- é o link para mandar a
alguém e o que o buscador lê -- e a página abre com ele em foco. Trocar
de jogo dentro da página não recarrega nada: o script troca o jogo e o
endereço juntos. Sem JavaScript, a página continua dizendo o que é cada
jogo e como se joga, e o seletor é uma lista de links.

Quem não entrou na conta joga uma partida de cada jogo; o fim de cada
partida chega em /jogos/partida/ e o ranking (do jogo e geral) sai de
/jogos/ranking/. As regras moram em `core/ranking.py`.
"""

import json

from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.generic import View

from sistema_interno.templatetags.interno_extras import estatico

from . import arena, ranking
from .models import Brinquedos
from .views_arena import WHATSAPP


def maquinas_dos_jogos():
    """Para cada jogo, a máquina do catálogo que é ele (pelo nome)."""
    maquinas = {}
    brinquedos = (
        Brinquedos.objects
        .filter(ativo=True)
        .only("id", "nome_brinquedo")
        .order_by("nome_brinquedo")
    )
    for brinquedo in brinquedos:
        slug = arena.jogo_da_maquina(brinquedo.nome_brinquedo)
        if not slug:
            continue
        maquinas.setdefault(slug, {
            "url": reverse("brinquedo_detalhe", args=[brinquedo.pk]) + "#bread",
            "nome": brinquedo.nome_brinquedo,
        })
    return maquinas


def _para_o_script(jogo):
    """O que o simulador precisa de um jogo, com os endereços já versionados."""
    controle = jogo["controle"]
    return {
        "slug": jogo["slug"],
        "titulo": jogo["titulo"],
        "maquina": jogo["maquina"],
        "chamada": jogo["chamada"],
        "descricao": jogo["descricao"],
        "comandos": jogo["comandos"],
        "cor": jogo["cor"],
        "capa": estatico(jogo["capa"]),
        "miniatura": estatico(jogo["miniatura"]),
        "poster": estatico(jogo["poster"]),
        "script": estatico(jogo["script"]),
        "variante": jogo.get("variante", ""),
        "url": jogo["url"],
        "maquinaUrl": jogo["maquina_url"],
        "maquinaNome": jogo["maquina_nome"],
        "gesto": controle["gesto"],
        "rotulo": controle["rotulo"],
        "icone": jogo["icone_gesto"],
        "passos": list(controle["passos"]),
        "naMaquina": controle["na_maquina"],
        "teclado": controle.get("teclado", ""),
        "botoes": [dict(b) for b in controle["botoes"]],
    }


@method_decorator(ensure_csrf_cookie, name="get")
class SimuladorView(View):
    def get(self, request, slug=None):
        if slug is not None and slug not in arena.JOGOS_POR_SLUG:
            raise Http404("Jogo não encontrado")

        maquinas = maquinas_dos_jogos()
        jogos = []
        for jogo in arena.jogos_do_simulador(arena.JOGOS):
            maquina = maquinas.get(jogo["slug"])
            jogos.append({
                **jogo,
                "maquina_url": maquina["url"] if maquina else "",
                "maquina_nome": maquina["nome"] if maquina else "",
            })
        atual = next((j for j in jogos if j["slug"] == slug), jogos[0])
        painel = ranking.painel(request, atual["slug"])
        voltar = atual["url"]
        salvos = ranking.salvos_agora(request)

        return render(request, "jogos.html", {
            "jogos": jogos,
            "atual": atual,
            "jogo_escolhido": slug is not None,
            "jogos_script": [_para_o_script(j) for j in jogos],
            "whatsapp": WHATSAPP,
            "ranking": painel,
            "salvos": salvos,
            "jogador": {
                **painel,
                "partidaUrl": reverse("jogos_partida"),
                "rankingUrl": reverse("jogos_ranking"),
                "cadastroUrl": reverse("registrar"),
                "entrarUrl": reverse("login"),
                "voltar": voltar,
            },
        })


class PartidaJogoView(View):
    """O fim de uma partida: grava o recorde (ou a partida grátis do visitante)."""

    def post(self, request):
        try:
            dados = json.loads(request.body or b"{}")
        except ValueError:
            return JsonResponse({"erro": "corpo inválido"}, status=400)
        try:
            resposta = ranking.registrar_partida(request, dados.get("jogo"), dados.get("pontos"))
        except ranking.PartidaInvalida as erro:
            return JsonResponse({"erro": str(erro)}, status=400)
        return JsonResponse(resposta)


@method_decorator(never_cache, name="get")
class RankingJogosView(View):
    """Os dois rankings e a posição de quem está vendo (por isso sem cache)."""

    def get(self, request):
        jogo = request.GET.get("jogo") or ""
        if jogo not in arena.JOGOS_POR_SLUG:
            return JsonResponse({"erro": "jogo desconhecido"}, status=404)
        return JsonResponse(ranking.painel(request, jogo))
