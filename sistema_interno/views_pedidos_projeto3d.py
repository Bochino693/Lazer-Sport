"""PROJETOS 3D DO SITE (Comercial > Projetos 3D do site): os pedidos do "Monte seu projeto".

O cliente monta o espaço no site (/monte-seu-projeto/, core/projeto3d.py) e
pede o projeto. Aqui a equipe comercial vê a lista (o tamanho, o modelo, o
que coube e o que ficou de fora), abre a ficha com o MESMO 3D que o cliente
viu (o app do site em modo "painel", refeito da escolha e da semente
guardadas), chama no WhatsApp e anota a situação. As fotos do espaço que o
cliente mandou aparecem na ficha, com o projeto montado nelas, e o app abre
cada uma com os pontos que ele marcou (para ver o projeto como estiver aqui).

Quem entra: a equipe comercial (Vendas, Ambulante, Gestão), como as
outras telas de cliente. Sem a tabela (a migração ainda não rodou), a tela
avisa em vez de cair.
"""

from __future__ import annotations

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import DatabaseError
from django.shortcuts import get_object_or_404, redirect, render

from core import projeto3d
from core.models import FotoDoEspaco, PedidoProjeto3D
from core import objetos_3d

from .views import GestorInternoRequiredMixin

POR_PAGINA = 25


def _tabela():
    # pelo módulo, na hora: quem importa a função guarda a de quando importou
    return objetos_3d.tabela_pronta(PedidoProjeto3D)


def _fotos(pedido):
    """As fotos do espaço do pedido, cada uma com a sua montagem (se veio): [{foto, montagem}]."""
    if not objetos_3d.tabela_pronta(FotoDoEspaco):
        return []
    try:
        todas = list(pedido.fotos.all())
    except DatabaseError:
        return []
    fotos = [f for f in todas if f.tipo == "foto"]
    montagens = [f for f in todas if f.tipo == "montagem"]
    # a montagem vem logo depois da sua foto (o id seguinte): casa pela ordem de chegada
    pares = []
    for f in fotos:
        par = next((m for m in montagens if m.id > f.id and all(not (f.id < o.id < m.id) for o in fotos)), None)
        pares.append({"foto": f, "montagem": par})
    return pares


class PedidosProjeto3DView(GestorInternoRequiredMixin):
    def get(self, request):
        if not _tabela():
            return render(request, "pedidos_projeto3d_inner.html", {"tabela_ausente": True})
        status = request.GET.get("status", "")
        pedidos = PedidoProjeto3D.objects.all()
        if status in dict(PedidoProjeto3D.STATUS):
            pedidos = pedidos.filter(status=status)
        contagem = {chave: 0 for chave, _ in PedidoProjeto3D.STATUS}
        try:
            for linha in PedidoProjeto3D.objects.values_list("status", flat=True):
                contagem[linha] = contagem.get(linha, 0) + 1
        except DatabaseError:
            pass
        pagina = Paginator(pedidos, POR_PAGINA).get_page(request.GET.get("page"))
        return render(request, "pedidos_projeto3d_inner.html", {
            "page_obj": pagina,
            "pedidos": pagina.object_list,
            "status_atual": status,
            "situacoes": [(chave, nome, contagem.get(chave, 0)) for chave, nome in PedidoProjeto3D.STATUS],
            "total": sum(contagem.values()),
        })


class PedidoProjeto3DView(GestorInternoRequiredMixin):
    def get(self, request, pk):
        if not _tabela():
            return redirect("pedidos_projeto_3d")
        pedido = get_object_or_404(PedidoProjeto3D, pk=pk)
        escolhas = pedido.escolhas or {}
        estado = {
            "espaco": {
                "largura": float(pedido.largura),
                "comprimento": float(pedido.comprimento),
                "pe_direito": float(pedido.pe_direito) if pedido.pe_direito else 4,
            },
            "principal": escolhas.get("principal"),
            "areas": escolhas.get("areas") or [],
            "itens": escolhas.get("itens") or [],
            "estilo": escolhas.get("estilo") or pedido.estilo,
            "cor": escolhas.get("cor") or pedido.cor,
            "semente": escolhas.get("semente") or pedido.semente,
            "opcoes": escolhas.get("opcoes") or {},
        }
        resumo = pedido.resumo or {}
        whatsapp = pedido.whatsapp if pedido.whatsapp.startswith("55") else "55" + pedido.whatsapp
        fotos = _fotos(pedido)
        return render(request, "pedido_projeto3d_inner.html", {
            "pedido": pedido,
            "projeto_dados": projeto3d.catalogo(),
            "projeto_estado": estado,
            "coube": resumo.get("coube") or [],
            "ficou_de_fora": resumo.get("ficou_de_fora") or [],
            "numeros": resumo.get("numeros") or {},
            "espaco_para_tudo": resumo.get("espaco_para_tudo") or {},
            "whatsapp": whatsapp,
            "situacoes": PedidoProjeto3D.STATUS,
            "fotos": fotos,
            # para o app: a foto e os pontos marcados (o projeto entra na foto como estiver montado aqui)
            "projeto_fotos": [{"url": p["foto"].url, "cantos": p["foto"].cantos or {}} for p in fotos if p["foto"].url],
        })

    def post(self, request, pk):
        if not _tabela():
            return redirect("pedidos_projeto_3d")
        pedido = get_object_or_404(PedidoProjeto3D, pk=pk)
        status = request.POST.get("status", pedido.status)
        if status in dict(PedidoProjeto3D.STATUS):
            pedido.status = status
        pedido.anotacao = (request.POST.get("anotacao") or "").strip()[:4000]
        pedido.save(update_fields=["status", "anotacao", "atualizado"])
        messages.success(request, f"Pedido nº {pedido.pk} atualizado.")
        return redirect("pedido_projeto_3d", pk=pedido.pk)
