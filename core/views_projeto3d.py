"""Monte seu projeto (/monte-seu-projeto/): a página e o pedido (as regras: core/projeto3d.py).

A página abre inteira sem JavaScript: as áreas e as máquinas do catálogo
com as medidas, como lista, e o botão do WhatsApp. Com JavaScript (e
WebGL), vira o app: as escolhas de um lado, o 3D do outro.

O pedido é público (não pede conta): por isso tem a armadilha para robôs
(um campo que só robô preenche), um teto por endereço (5 por hora) e o
tamanho de tudo conferido. Não se guarda IP: o teto vive só no cache.
"""

from __future__ import annotations

import hashlib
import json
import logging
from urllib.parse import quote

from django.core.cache import cache
from django.db import DatabaseError, transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import ensure_csrf_cookie

from . import projeto3d
from .registro_cadastro import ip_da_requisicao

logger = logging.getLogger(__name__)

WHATSAPP = "5511960563135"
#: Quantos pedidos um mesmo endereço pode mandar por hora (gente de verdade manda um ou dois).
PEDIDOS_POR_HORA = 5
#: O corpo do pedido (a escolha e o resumo) nunca passa disto.
TAMANHO_MAXIMO = 64 * 1024


def _chave_do_teto(request):
    ip, _ = ip_da_requisicao(request)
    # só o resumo do endereço, e só no cache (some em uma hora)
    return "projeto3d:pedidos:" + hashlib.sha256((ip or "sem-ip").encode()).hexdigest()[:24]


def texto_do_whatsapp(campos):
    """A mensagem pronta para o WhatsApp: o tamanho, o modelo e o que entrou."""
    linhas = [
        "Olá! Montei meu projeto no site da Lazer & Sport.",
        f"Espaço: {campos['largura']} × {campos['comprimento']} m" + (f", pé-direito {campos['pe_direito']} m" if campos.get("pe_direito") else ""),
        f"Modelo: {campos['principal']}",
    ]
    coube = (campos.get("resumo") or {}).get("coube") or []
    if coube:
        linhas.append("Com: " + ", ".join(f"{c.get('qtd', '1')}× {c.get('nome', '')}" for c in coube[:20]))
    return "\n".join(linhas)


@method_decorator(ensure_csrf_cookie, name="dispatch")
class MonteSeuProjetoView(View):
    def get(self, request):
        dados = projeto3d.catalogo()
        usuario = request.user if request.user.is_authenticated else None
        return render(request, "monte_seu_projeto.html", {
            "projeto_dados": dados,
            "areas": [{"chave": k, **v} for k, v in projeto3d.AREAS.items()],
            "maquinas": [i for i in dados["itens"] if i["tipo"] == "maquina"],
            "grandes": [i for i in dados["itens"] if i["tipo"] == "grande"],
            "contato_inicial": {
                "nome": (usuario.get_full_name() or usuario.username) if usuario else "",
                "email": usuario.email if usuario else "",
                "whatsapp": (getattr(getattr(usuario, "perfil", None), "telefone", "") or "") if usuario else "",
            },
            "whatsapp": WHATSAPP,
        })


class PedirProjeto3DView(View):
    """POST JSON: {contato, espaco, escolha, resumo, site (a armadilha)} -> {status, numero}."""

    def post(self, request):
        if len(request.body or b"") > TAMANHO_MAXIMO:
            return JsonResponse({"status": "erro", "mensagem": "O pedido ficou grande demais."}, status=413)
        try:
            dados = json.loads(request.body or b"{}")
        except (ValueError, UnicodeDecodeError):
            return JsonResponse({"status": "erro", "mensagem": "Pedido em formato inválido."}, status=400)
        if not isinstance(dados, dict):
            return JsonResponse({"status": "erro", "mensagem": "Pedido em formato inválido."}, status=400)

        # a armadilha: o campo escondido que só robô preenche -- responde como se fosse, e não grava
        if str(dados.get("site") or "").strip():
            return JsonResponse({"status": "sucesso", "numero": 0})

        chave = _chave_do_teto(request)
        if cache.get(chave, 0) >= PEDIDOS_POR_HORA:
            return JsonResponse({
                "status": "erro",
                "mensagem": "Recebemos vários pedidos daqui agora há pouco. Fale com a gente pelo WhatsApp.",
            }, status=429)

        try:
            campos = projeto3d.validar_pedido(dados, projeto3d.catalogo())
        except projeto3d.PedidoInvalido as erro:
            return JsonResponse({"status": "erro", "mensagem": str(erro)}, status=400)

        from .models import PedidoProjeto3D

        try:
            with transaction.atomic():
                pedido = PedidoProjeto3D.objects.create(
                    usuario=request.user if request.user.is_authenticated else None, **campos,
                )
        except DatabaseError:
            # o banco sem a tabela (a migração ainda não rodou): o cliente não perde o projeto
            logger.exception("Monte seu projeto: o pedido não foi gravado")
            return JsonResponse({
                "status": "erro",
                "mensagem": "Não conseguimos gravar agora. Mande pelo WhatsApp: a mensagem já vai pronta.",
                "whatsapp": f"https://wa.me/{WHATSAPP}?text={quote(texto_do_whatsapp(campos))}",
            }, status=503)

        try:
            cache.add(chave, 0, 3600)
            cache.incr(chave)
        except ValueError:
            cache.set(chave, 1, 3600)
        mensagem = texto_do_whatsapp(campos) + f"\nPedido nº {pedido.pk}"
        return JsonResponse({
            "status": "sucesso",
            "numero": pedido.pk,
            "whatsapp": f"https://wa.me/{WHATSAPP}?text={quote(mensagem)}",
        })
