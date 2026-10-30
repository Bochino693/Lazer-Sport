"""Arena e Lazer & Sport Jogos: os jogos da casa e as máquinas da fábrica.

A página tem de abrir inteira sem JavaScript: os brinquedos chegam como
uma lista de links (é o que o buscador lê e o que aparece num aparelho
sem JavaScript), e os jogos como cartões com a arte e a descrição. As
máquinas vêm em seções: as dos jogos da casa, as que já fazíamos e os
trampolins e brinquedões.
"""

from django.db.models import Prefetch
from django.shortcuts import render
from django.urls import reverse
from django.views.generic import View

from . import arena
from .models import Brinquedos, ImagemBrinquedo

WHATSAPP = "5511960563135"


def brinquedos_da_arena():
    """Os brinquedos ativos com tudo o que a arena desenha, em quatro consultas."""
    return (
        Brinquedos.objects
        .filter(ativo=True)
        .only(
            "id", "nome_brinquedo", "imagem_brinquedo", "descricao",
            "valor_brinquedo", "exibir_na_loja", "avaliacao", "voltz",
            "altura_m", "largura_m", "profundidade_m",
        )
        .prefetch_related(
            "categorias_brinquedos",
            "tags",
            Prefetch(
                "imagens_brinquedo",
                queryset=ImagemBrinquedo.objects.order_by("ordem", "id"),
            ),
        )
        .order_by("nome_brinquedo")
    )


def jogos_com_maquina(dados):
    """Cada jogo com o link da máquina de verdade, quando ela está no catálogo."""
    jogos = []
    for jogo in arena.JOGOS:
        maquina = next((b for b in dados if b["jogo"] == jogo["slug"]), None)
        jogos.append({
            **jogo,
            "maquina_url": maquina["url"] if maquina else "",
            "maquina_nome": maquina["nome"] if maquina else "",
        })
    return jogos


class ArenaView(View):
    def get(self, request):
        dados = [
            arena.dados_do_brinquedo(
                brinquedo,
                reverse("brinquedo_detalhe", args=[brinquedo.pk]) + "#bread",
            )
            for brinquedo in brinquedos_da_arena()
        ]

        # os objetos 3D que chegaram antes do cadastro: na arena, já aparecem
        na_arena = dados + arena.modelos_fora_do_catalogo(dados)
        categorias = sorted({c for b in na_arena for c in b["categorias"]})
        grupos = arena.grupos_da_arena(na_arena)
        jogos = jogos_com_maquina(dados)

        return render(request, "arena.html", {
            "grupos_arena": grupos,
            # a galeria de fotos é do catálogo (cada uma tem a sua página)
            "brinquedos_arena": dados,
            # o que o arena3d.js monta: as áreas e as máquinas com as fotos
            "arena_dados": {
                "zonas": [{k: g[k] for k in ("id", "titulo", "kicker")} for g in grupos],
                "maquinas": na_arena,
            },
            "categorias_arena": categorias,
            "jogos": jogos,
            "total_jogaveis": len(jogos),
            "whatsapp": WHATSAPP,
        })
