"""Arena e Lazer & Sport Jogos: os jogos da casa e as máquinas da fábrica.

A página tem de abrir inteira sem JavaScript: os brinquedos chegam como
uma lista de links (é o que o buscador lê e o que aparece num aparelho
sem JavaScript), e os jogos como cartões com a arte e a descrição. As
máquinas vêm em seções: as dos jogos da casa, as que já fazíamos e os
trampolins e brinquedões.
"""

from django.db.models import Prefetch
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from django.urls import reverse
from django.views.generic import View

from . import arena, projeto3d
from .home_cache import get_cached_catalog_page
from .models import Brinquedos, ImagemBrinquedo
from .objetos_3d import prefetch_do_objeto
from .views_projeto3d import contexto_do_projeto

WHATSAPP = "5511960563135"


def brinquedos_da_arena():
    """Os brinquedos ativos com tudo o que a arena desenha, em cinco consultas."""
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
            # o 3D do cadastro (sem a tabela ainda, a arena segue sem ele)
            *prefetch_do_objeto(),
            Prefetch(
                "imagens_brinquedo",
                queryset=ImagemBrinquedo.objects.order_by("ordem", "id"),
            ),
        )
        .order_by("nome_brinquedo")
    )


def dados_publicos_da_arena():
    """Tudo o que a Arena mostra igual para todo visitante (vai para o cache do catálogo).

    POR QUE EM CACHE. A Arena não tinha cache nenhum: cada visita lia os
    brinquedos com categorias, tags, fotos e objeto 3D DUAS vezes (uma para
    a roda e a galeria, outra para o "Monte seu espaço") e passava cada um
    pelas regras de desenho -- dez consultas e ~110 ms de CPU por visita,
    ~2,7 s no ar com o banco pela rede (LEIA-ME-V10, seção 63). Agora os
    brinquedos são lidos uma vez, servem às duas partes, e o resultado vale
    até alguém mexer no catálogo (a versão muda nos signals). Fica de fora
    só o contato de quem está logado, que o formulário do pedido preenche.
    """
    dados = [
        arena.dados_do_brinquedo(
            brinquedo,
            reverse("brinquedo_detalhe", args=[brinquedo.pk]) + "#bread",
        )
        for brinquedo in brinquedos_da_arena()
    ]

    # os objetos 3D que chegaram antes do cadastro: na arena, já aparecem
    na_arena = dados + arena.modelos_fora_do_catalogo(dados)
    # a roda 3D só com quem tem objeto 3D de verdade (.glb); as áreas
    # (e a lista, que é a roda sem WebGL) saem dela: área vazia some
    na_roda = arena.na_roda_3d(na_arena)
    grupos = arena.grupos_da_arena(na_roda)

    return {
        # o catálogo do "Monte seu espaço" (core/projeto3d.py), dos mesmos brinquedos
        "projeto_dados": projeto3d.catalogo(na_arena),
        "grupos_arena": grupos,
        # "Todas as máquinas da fábrica": o catálogo e os objetos 3D que
        # ainda não estão nele (o Strike Kids antes do cadastro), por nome
        "brinquedos_arena": sorted(na_arena, key=lambda b: arena._normalizar(b["nome"])),
        # o que o arena3d.js monta: as áreas e as máquinas com o objeto 3D
        "arena_dados": {
            "zonas": [{k: g[k] for k in ("id", "titulo", "kicker")} for g in grupos],
            "maquinas": na_roda,
        },
        # o filtro da roda (só as categorias de quem está nela) e o da galeria
        "categorias_roda": sorted({c for b in na_roda for c in b["categorias"]}),
        "categorias_arena": sorted({c for b in na_arena for c in b["categorias"]}),
    }


@method_decorator(ensure_csrf_cookie, name="dispatch")
class ArenaView(View):
    """A Arena 3D: os objetos 3D da fábrica num parque e o "Monte seu espaço".

    Os jogos foram para o portal Lazer & Sport Games (/jogos/): aqui fica só
    o 3D -- ver os brinquedos e montar o espaço do cliente pela medida dele,
    com o pedido do projeto.
    """

    def get(self, request):
        publicos = dict(get_cached_catalog_page("arena", (), dados_publicos_da_arena))
        projeto_dados = publicos.pop("projeto_dados")

        return render(request, "arena.html", {
            # o "Monte seu espaço" (core/projeto3d.py): o catálogo, as áreas e o contato
            **contexto_do_projeto(request, projeto_dados),
            **publicos,
            "whatsapp": WHATSAPP,
        })
