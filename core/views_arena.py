"""Arena 3D e Lazer & Sport Jogos: os jogos da casa e as máquinas em 3D.

A página tem de abrir inteira sem JavaScript: os brinquedos chegam como
uma lista de links (é o que o buscador lê e o que aparece num aparelho
sem WebGL), e os jogos como cartões com a arte e a descrição. O 3D e as
miniaturas jogáveis entram por cima disso, quando o aparelho aguenta.
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
            "valor_brinquedo", "avaliacao", "voltz",
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
        maquina = next((b for b in dados if b["desenho"] in jogo["desenhos"]), None)
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

        categorias = sorted({c for b in dados for c in b["categorias"]})
        jogos = jogos_com_maquina(dados)

        return render(request, "arena.html", {
            # Em 3D só as máquinas com objeto de verdade; o catálogo
            # inteiro vai para a vitrine de fotos logo abaixo.
            "maquinas_3d": arena.maquinas_3d(dados),
            "brinquedos_arena": dados,
            "categorias_arena": categorias,
            "jogos": jogos,
            "total_jogaveis": len(jogos),
            "whatsapp": WHATSAPP,
        })
