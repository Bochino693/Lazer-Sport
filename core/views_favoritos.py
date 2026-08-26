"""Curtir e guardar na lista de desejos, com ou sem conta.

O endpoint de alternância responde JSON e é o mesmo para o site e para o
app híbrido. O app nativo usa a API em ``core/api/favoritos_views.py``,
que compartilha as regras de ``core/favoritos.py``.
"""

from __future__ import annotations

import json

from django.http import JsonResponse
from django.shortcuts import render
from django.views import View
from django.views.decorators.http import require_POST

from . import favoritos as servico
from .models import Favorito


def _corpo(request) -> dict:
    """Aceita JSON (fetch) e formulário (fallback sem JavaScript)."""
    if request.content_type and "application/json" in request.content_type:
        try:
            dados = json.loads(request.body or b"{}")
        except (ValueError, UnicodeDecodeError):
            return {}
        return dados if isinstance(dados, dict) else {}
    return request.POST.dict()


@require_POST
def alternar_favorito(request):
    dados = _corpo(request)

    try:
        tipo = servico.normalizar_tipo(dados.get("tipo"))
        produto = servico.buscar_produto(
            dados.get("produto"),
            dados.get("id"),
        )
    except servico.TipoInvalido:
        return JsonResponse(
            {"ok": False, "erro": "Tipo de interação inválido."},
            status=400,
        )
    except servico.ProdutoInvalido:
        return JsonResponse(
            {"ok": False, "erro": "Produto não encontrado."},
            status=404,
        )

    # CURTIR É EXCLUSIVO DO APLICATIVO.
    #
    # O site mostra quantas curtidas o produto tem -- é prova social e
    # ajuda a escolher --, mas quem curte é quem instalou o aplicativo.
    # A regra é o que dá valor ao aplicativo: o ponto que vira cupom
    # nasce lá dentro. Guardar na lista de desejos continua valendo em
    # qualquer lugar, porque essa é a porta de entrada.
    if tipo == Favorito.Tipo.CURTIDA:
        return JsonResponse(
            {
                "ok": False,
                "erro": (
                    "As curtidas são exclusivas do aplicativo Lazer & Sport. "
                    "Instale para curtir, juntar pontos e trocar por cupons."
                ),
                "somente_app": True,
            },
            status=403,
        )

    estado = servico.alternar(
        request,
        tipo,
        produto,
        origem=Favorito.Origem.SITE,
    )
    estado["ok"] = True
    estado["logado"] = servico.usuario_logado(request) is not None
    estado["total_desejos"] = servico.meus_favoritos(
        request,
        Favorito.Tipo.DESEJO,
    ).count()

    return servico.aplicar_cookie(request, JsonResponse(estado))


def meus_favoritos(request):
    """GET: o que ESTE visitante marcou, para o JS pintar os cards.

    POR QUE UM ENDEREÇO SÓ PARA ISSO. A home do site é cacheada e servida
    igual para todo mundo -- é o que a mantém rápida. Um card renderizado
    já marcado vazaria a lista de uma pessoa para as outras. Então o HTML
    sai neutro e o estado de quem está olhando chega aqui, em uma chamada
    por página.
    """
    marcados = servico.ids_marcados(request, Favorito.Tipo.DESEJO)

    resposta = JsonResponse({
        "ok": True,
        "desejo": {
            "brinquedo": sorted(marcados["brinquedo"]),
            "peca": sorted(marcados["peca"]),
        },
        "total_desejos": len(marcados["brinquedo"]) + len(marcados["peca"]),
        "logado": servico.usuario_logado(request) is not None,
    })

    # Sem marcação nenhuma não vale criar chave de aparelho: o visitante
    # que só passou pela home não precisa sair daqui com cookie.
    if not marcados["brinquedo"] and not marcados["peca"]:
        return resposta

    return servico.aplicar_cookie(request, resposta)


class ListaDesejosView(View):
    """A lista funciona sem login: visitante vê a do próprio aparelho."""

    template_name = "lista_desejos.html"

    def get(self, request):
        desejos = (
            servico.meus_favoritos(request, Favorito.Tipo.DESEJO)
            .select_related("brinquedo", "peca")
            .prefetch_related("peca__imagem_peca_reposicao")
        )
        curtidos = servico.ids_marcados(request, Favorito.Tipo.CURTIDA)

        brinquedos = [i.brinquedo for i in desejos if i.brinquedo_id and i.brinquedo]
        pecas = [i.peca for i in desejos if i.peca_id and i.peca]

        totais_brinquedos = servico.contagem_curtidas(brinquedos)
        totais_pecas = servico.contagem_curtidas(pecas)

        # O template só desenha: quem sabe se está curtido e quantas
        # curtidas o produto tem é a view, em duas consultas no total.
        cartoes_brinquedos = [
            {
                "obj": brinquedo,
                "curtido": brinquedo.pk in curtidos["brinquedo"],
                "curtidas": totais_brinquedos.get(brinquedo.pk, 0),
            }
            for brinquedo in brinquedos
        ]
        cartoes_pecas = [
            {
                "obj": peca,
                "curtido": peca.pk in curtidos["peca"],
                "curtidas": totais_pecas.get(peca.pk, 0),
            }
            for peca in pecas
        ]

        # O programa de pontos aparece aqui de propósito: esta é a tela de
        # quem já demonstrou interesse. É o melhor lugar do site para
        # mostrar quanto falta para a próxima meta -- e que curtir, no
        # aplicativo, também vale ponto.
        from . import pontos as servico_pontos

        contexto = {
            "cartoes_brinquedos": cartoes_brinquedos,
            "cartoes_pecas": cartoes_pecas,
            "total_desejos": len(cartoes_brinquedos) + len(cartoes_pecas),
            "total_curtidas": (
                len(curtidos["brinquedo"]) + len(curtidos["peca"])
            ),
            # Visitante sem conta vê as metas com o progresso do próprio
            # aparelho: é a barra em "2 de 5" que faz criar cadastro.
            "pontos": servico_pontos.progresso(
                servico.usuario_logado(request),
                curtidas=len(curtidos["brinquedo"]) + len(curtidos["peca"]),
                desejos=len(cartoes_brinquedos) + len(cartoes_pecas),
            ),
        }

        resposta = render(request, self.template_name, contexto)
        return servico.aplicar_cookie(request, resposta)
