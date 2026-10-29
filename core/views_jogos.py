"""O simulador: a área dedicada às prévias dos jogos das máquinas.

Cada jogo tem o seu endereço (/jogos/<jogo>/) -- é o link para mandar a
alguém e o que o buscador lê -- e a página abre com ele em foco. Trocar
de jogo dentro da página não recarrega nada: o script troca o jogo e o
endereço juntos. Sem JavaScript, a página continua dizendo o que é cada
jogo e como se joga, e o seletor é uma lista de links.
"""

from django.http import Http404
from django.shortcuts import render
from django.urls import reverse
from django.views.generic import View

from sistema_interno.templatetags.interno_extras import estatico

from . import arena
from .models import Brinquedos
from .views_arena import WHATSAPP


def maquinas_dos_jogos():
    """Para cada tipo de máquina, o primeiro brinquedo do catálogo que é dele."""
    maquinas = {}
    brinquedos = (
        Brinquedos.objects
        .filter(ativo=True)
        .only("id", "nome_brinquedo")
        .prefetch_related("categorias_brinquedos", "tags")
        .order_by("nome_brinquedo")
    )
    for brinquedo in brinquedos:
        desenho = arena.modelo_3d(
            brinquedo.nome_brinquedo,
            [c.nome_categoria for c in brinquedo.categorias_brinquedos.all() if c.nome_categoria],
            [t.nome_tags for t in brinquedo.tags.all() if t.nome_tags],
        )
        maquinas.setdefault(desenho, {
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
        "botoes": [dict(b) for b in controle["botoes"]],
    }


class SimuladorView(View):
    def get(self, request, slug=None):
        if slug is not None and slug not in arena.JOGOS_POR_SLUG:
            raise Http404("Jogo não encontrado")

        maquinas = maquinas_dos_jogos()
        jogos = []
        for jogo in arena.jogos_do_simulador(arena.JOGOS):
            maquina = next((maquinas[d] for d in jogo["desenhos"] if d in maquinas), None)
            jogos.append({
                **jogo,
                "maquina_url": maquina["url"] if maquina else "",
                "maquina_nome": maquina["nome"] if maquina else "",
            })
        atual = next((j for j in jogos if j["slug"] == slug), jogos[0])

        return render(request, "jogos.html", {
            "jogos": jogos,
            "atual": atual,
            "jogo_escolhido": slug is not None,
            "jogos_script": [_para_o_script(j) for j in jogos],
            "whatsapp": WHATSAPP,
        })
