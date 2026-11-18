"""As páginas do kit eletrônico: /kits/ e /kits/<id>/ (LEIA-ME seção 105).

O dono: o kit "deve ter espaço entre os demais produtos". O espaço é uma
vitrine própria -- a lista dos kits, com um topo que explica o que é um kit
(a parte eletrônica completa para montar ou recuperar a máquina, pronta para
instalar) -- e a página de cada kit, que é a página da peça
(reposicao_info.html) com o que só o kit tem: "O que vem no kit" e "Para a
máquina X". Os kits NÃO aparecem na lista de peças (/pecas-reposicao/).

Como as outras telas do catálogo, o que é igual para todo visitante sai do
cache do catálogo (core/home_cache.py) -- a versão muda quando a equipe salva
um kit ou um item dele (core/signals.py) -- e o que é DESTE visitante (o que
ele curtiu ou guardou) é resolvido a cada requisição.
"""

from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from . import favoritos as servico_favoritos
from . import kits
from .home_cache import get_cached_catalog_page
from .models import PecasReposicao


def _url_da_peca_avulsa(componente):
    """A página da peça vendida sozinha (o Cabo HDMI), só se ela está na vitrine."""
    peca = componente.peca
    if peca is None or peca.eh_kit or not peca.ativo or peca.uso != PecasReposicao.Uso.LOJA:
        return ""
    return peca.url_publica


class KitsView(View):
    """/kits/: a vitrine dos kits eletrônicos."""

    @staticmethod
    def _montar():
        kits = list(PecasReposicao.kits_da_vitrine())
        return {
            "kits": kits,
            "curtidas": servico_favoritos.contagem_curtidas(kits),
        }

    def get(self, request):
        from .views import _marcas_do_visitante

        dados = get_cached_catalog_page("kits", (), self._montar)
        totais = dados["curtidas"]
        # o kit é uma peça também nas curtidas e na lista de desejos
        marcas = _marcas_do_visitante(request, "peca")

        cartoes = [
            {
                "obj": kit,
                "curtido": kit.pk in marcas["curtida"],
                "desejado": kit.pk in marcas["desejo"],
                "curtidas": totais.get(kit.pk, 0),
            }
            for kit in dados["kits"]
        ]
        maquinas = {kit.maquina.nome_brinquedo for kit in dados["kits"] if kit.maquina_id and kit.maquina}
        resposta = render(request, "kits.html", {
            "cartoes_kits": cartoes,
            "total_maquinas": len(maquinas),
        })
        return servico_favoritos.aplicar_cookie(request, resposta)


class KitDetalheView(View):
    """/kits/<id>/: a página do kit (a da peça, com os itens e a máquina)."""

    @staticmethod
    def _montar(pk):
        kit = get_object_or_404(PecasReposicao.kits_da_vitrine(), pk=pk)
        componentes = [
            {
                "nome": item.nome,
                "detalhe": item.detalhe,
                "quantidade": item.quantidade,
                "icone": item.icone,
                "foto": kits.foto_do_componente(item),
                "url_peca": _url_da_peca_avulsa(item),
            }
            for item in kit.componentes_kit.select_related("peca").prefetch_related("peca__imagem_peca_reposicao")
        ]
        maquina = kit.maquina if (kit.maquina_id and kit.maquina and kit.maquina.ativo) else None
        imagens = list(kit.imagens_ordenadas)
        return {
            "peca": kit,
            "imagens_peca": imagens,
            "categorias_peca": list(kit.categoria_peca.all()),
            "componentes": componentes,
            "maquina_kit": maquina,
            # sem foto própria, a vitrine mostra a máquina com o selo "KIT ELETRÔNICO"
            "foto_da_maquina": kit.foto_do_card if (not imagens and kit.foto_e_da_maquina) else None,
            "curtidas": servico_favoritos.contagem_curtidas([kit]).get(kit.pk, 0),
        }

    def get(self, request, pk):
        from django.http import Http404

        from . import cliques
        from .interacoes import VISITA, inicio_da_hora, somar
        from .views import _estado_do_visitante

        try:
            dados = get_cached_catalog_page("kit", (pk,), lambda: KitDetalheView._montar(pk))
        except Http404:
            # o endereço de kit com o número de uma peça avulsa leva à peça
            if PecasReposicao.pecas_avulsas_da_vitrine().filter(pk=pk).exists():
                return redirect("reposicao_detalhe", pk=pk, permanent=True)
            raise
        kit = dados["peca"]

        # a visita vai para o gráfico do painel, como a da peça
        cliques.depois(somar, VISITA, "peca", kit.pk, 1, inicio_da_hora())

        resposta = render(request, "reposicao_info.html", {
            "peca": kit,
            "eh_kit": True,
            "imagens_peca": dados["imagens_peca"],
            "categorias_peca": dados["categorias_peca"],
            "componentes": dados["componentes"],
            "maquina_kit": dados["maquina_kit"],
            "foto_da_maquina": dados["foto_da_maquina"],
            "favorito": _estado_do_visitante(request, kit, dados["curtidas"]),
        })
        return servico_favoritos.aplicar_cookie(request, resposta)
