"""AS ASSINATURAS NUM LUGAR SÓ (LEIA-ME-V10, seção 137).

O pedido do dono: "e no sistema interno ter com facilidade e orientado com
os objetos as assinaturas, para fáceis impressões e etc."

Até aqui a assinatura só se achava entrando em cada orçamento ou em cada
ordem de serviço. Esta tela junta os documentos que o cliente assina no
celular (`DocumentoAssinatura`), em cards, organizados pelo OBJETO a que
pertencem -- o orçamento (contrato de compra e venda, termo de compra ou a
ordem de serviço que sai dele) e a ordem de serviço --, com o PDF a um
toque e o caminho de volta para o objeto.

Nada de tabela nova nem de regra nova: a lista só LÊ. Imprimir, baixar,
abrir o QR e gerar o link continuam nas telas de cada objeto
(`views_documento_assinatura`, `views_assinatura_os`), que conferem a
permissão de novo.

QUEM VÊ O QUÊ (`permissoes.capacidades`), também por URL direta:

  * as assinaturas dos ORÇAMENTOS: quem gera o documento do orçamento
    (`assinaturas_orcamentos`: Vendas, Ambulante e Gestão) -- o Ambulante,
    só as da própria carteira (`limitar_orcamentos`) -- e o Financeiro, que
    só lê e imprime (sem o QR e o link);
  * as das ORDENS DE SERVIÇO: quem vê a O.S. (`assinaturas_os`: Produção,
    Financeiro e Gestão); o QR e o link, só quem edita a O.S.

O documento "substituído" (gerado de novo antes de alguém assinar) não
entra: nunca teve assinatura, e o link dele já não vale.

CONSULTAS (o banco fica a ~170 ms): duas, quaisquer que sejam os cards --
uma para os números dos chips (que também dá o total da página) e uma para
os cards, com o orçamento e a O.S. vindo junto (`select_related`) e sem o
traço em PNG de cada assinatura.
"""

from __future__ import annotations

import re
from urllib.parse import urlencode

from django.core.paginator import Paginator
from django.db.models import Case, Count, F, Q, When
from django.db.models.functions import Coalesce
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.generic import View

from . import documento_assinatura as svc
from .documento_servico import papel_curto
from .models import Cliente, DocumentoAssinatura
from .permissoes import (
    AMBULANTE, FINANCEIRO, GESTAO, PRODUCAO, VENDAS, capacidades,
)
from .views import InternoRequiredMixin

URLCONF = "sistema_interno.urls"

ASSINADO = DocumentoAssinatura.Situacao.ASSINADO
AGUARDANDO = DocumentoAssinatura.Situacao.AGUARDANDO

#: Os chips da situação e do objeto: (valor na URL, rótulo, ícone).
SITUACOES = (
    ("todas", "Todas", "bi-collection"),
    ("assinadas", "Assinadas", "bi-patch-check-fill"),
    ("aguardando", "Aguardando", "bi-hourglass-split"),
)
OBJETOS = (
    ("todos", "Todos os objetos", "bi-grid"),
    ("orcamentos", "Orçamentos", "bi-file-earmark-text-fill"),
    ("os", "Ordens de serviço", "bi-clipboard2-check-fill"),
    ("pedidos", "Pedidos do site", "bi-bag-check-fill"),
)
#: A capacidade que abre cada objeto (o chip só aparece para quem vê o objeto).
CAPACIDADE_DO_OBJETO = {
    "orcamentos": "assinaturas_orcamentos", "os": "assinaturas_os", "pedidos": "assinaturas_pedidos",
}

_DA_ORDEM = Q(orcamento__isnull=True, ordem_servico__isnull=False)
#: O contrato do pedido do site (seção 145): a terceira origem.
_DO_PEDIDO = Q(pedido__isnull=False)
_DO_ORCAMENTO = Q(orcamento__isnull=False)


def documentos_visiveis(user):
    """Os documentos que ESTA pessoa pode ver, pelo objeto de cada um."""
    acesso = capacidades(user)
    visiveis = Q(pk__in=[])
    if acesso["assinaturas_orcamentos"]:
        do_orcamento = _DO_ORCAMENTO
        if acesso["orcamentos_proprios"]:
            # a carteira do Ambulante: a mesma regra de `permissoes.limitar_orcamentos`
            do_orcamento &= Q(orcamento__responsavel=user)
        visiveis |= do_orcamento
    if acesso["assinaturas_os"]:
        visiveis |= _DA_ORDEM
    if acesso["assinaturas_pedidos"]:
        visiveis |= _DO_PEDIDO
    return (
        DocumentoAssinatura.objects
        .filter(visiveis)
        .filter(situacao__in=(ASSINADO, AGUARDANDO))
    )


def do_cliente(cliente_id) -> Q:
    """Os documentos DESTE cliente, pelo vínculo de verdade (seção 144).

    O contrato do orçamento ligado a ele, ou a ordem de serviço ligada a
    ele -- nunca pelo nome digitado (dois "Buffet Alegria" não se misturam).
    """
    return Q(orcamento__cliente_id=cliente_id) | (_DA_ORDEM & Q(ordem_servico__cliente_id=cliente_id))


def contagem_por_cliente(user, ids) -> dict:
    """{id do cliente: {"assinadas": n, "aguardando": n}} do que ESTA pessoa pode ver.

    Uma consulta para a página inteira da lista de clientes (o banco fica a
    ~170 ms): o cliente de cada documento é o do orçamento, ou o da O.S.
    quando o documento é dela. Só entra quem tem pelo menos um documento.
    """
    ids = [pk for pk in ids if pk]
    if not ids or not capacidades(user)["assinaturas"]:
        return {}
    linhas = (
        documentos_visiveis(user)
        .annotate(cliente_do_documento=Case(
            When(orcamento__isnull=False, then=F("orcamento__cliente_id")),
            default=F("ordem_servico__cliente_id"),
        ))
        .filter(cliente_do_documento__in=ids)
        .values("cliente_do_documento")
        .annotate(
            assinadas=Count("pk", filter=Q(situacao=ASSINADO)),
            aguardando=Count("pk", filter=Q(situacao=AGUARDANDO)),
        )
    )
    return {
        linha["cliente_do_documento"]: {"assinadas": linha["assinadas"], "aguardando": linha["aguardando"]}
        for linha in linhas
    }


def resumo_do_cliente(numeros) -> str:
    """"2 assinadas · 1 aguardando" (só o que existe)."""
    partes = []
    if numeros.get("assinadas"):
        partes.append(f"{numeros['assinadas']} assinada{'s' if numeros['assinadas'] != 1 else ''}")
    if numeros.get("aguardando"):
        partes.append(f"{numeros['aguardando']} aguardando")
    return " · ".join(partes)


def _numero_buscado(busca: str):
    """O número que a pessoa digitou: "12", "#12", "0012/2026", "OS-00012/2026"."""
    achado = re.search(r"\d+", busca)
    if not achado:
        return None
    numero = int(achado.group())
    return numero if 0 < numero < 2_000_000_000 else None


def _cartao(documento, acesso) -> dict:
    """O que um card mostra e para onde cada botão leva."""
    conteudo = documento.conteudo or {}
    if documento.pedido_id:
        return _cartao_do_pedido(documento, conteudo)
    orcamento = documento.orcamento if documento.orcamento_id else None
    ordem = None if orcamento is not None else documento.ordem_servico
    if orcamento is not None:
        pagina = reverse("documento_assinatura_inner", args=[orcamento.pk], urlconf=URLCONF)
        via = reverse("documento_assinatura_via", args=[orcamento.pk], urlconf=URLCONF)
        lista = reverse("orcamentos_inner", urlconf=URLCONF)
        objeto = {
            "tipo": "orcamento",
            "rotulo": f"Orçamento nº {orcamento.numero_documento}",
            "icone": "bi-file-earmark-text-fill",
            "url": f"{lista}?q={orcamento.pk}&editar={orcamento.pk}",
        }
        cliente = orcamento.nome_cliente
        # o QR e o link são de quem gera o documento (Comercial); o
        # Financeiro lê e imprime
        pode_qr = acesso["orcamentos_editar_comercial"]
        suspenso = not documento.assinado and bool(svc.motivo_da_suspensao(documento, orcamento))
    else:
        pagina = reverse("assinatura_os_inner", args=[ordem.pk], urlconf=URLCONF)
        via = reverse("assinatura_os_via", args=[ordem.pk], urlconf=URLCONF)
        lista = reverse("ordens_servico_inner", urlconf=URLCONF)
        pode_qr = acesso["ordens_servico_editar"]
        objeto = {
            "tipo": "os",
            "rotulo": f"O.S. {ordem.numero_documento}",
            "icone": "bi-clipboard2-check-fill",
            "url": f"{lista}?q={ordem.numero_documento}" + (f"&editar={ordem.pk}" if pode_qr else ""),
        }
        cliente = ordem.nome_cliente
        suspenso = not documento.assinado and bool(svc.motivo_da_suspensao(documento))
    via = f"{via}?documento={documento.pk}"
    return {
        "documento": documento,
        "objeto": objeto,
        "cliente": cliente or (conteudo.get("cliente") or {}).get("nome") or "Cliente sem nome",
        # o cadastro a que o documento está ligado (para ir ao cliente e para filtrar por ele)
        "cliente_id": orcamento.cliente_id if orcamento is not None else ordem.cliente_id,
        "papel": papel_curto(conteudo),
        "situacao": "assinado" if documento.assinado else ("suspenso" if suspenso else "aguardando"),
        "url_via": via,
        "url_imprimir": f"{via}&imprimir=1",
        "url_pagina": pagina,
        "pode_qr": pode_qr,
    }


def _cartao_do_pedido(documento, conteudo) -> dict:
    """O card do contrato de um pedido do site: a equipe só lê e imprime."""
    pedido = documento.pedido
    via = reverse("assinatura_pedido_via", args=[pedido.pk], urlconf=URLCONF) + f"?documento={documento.pk}"
    suspenso = not documento.assinado and pedido.status == "cancelado"
    return {
        "documento": documento,
        "objeto": {
            "tipo": "pedido",
            "rotulo": f"Pedido do site nº {pedido.pk}",
            "icone": "bi-bag-check-fill",
            "url": reverse("pedidos_inner", urlconf=URLCONF) + "?filtro=todos",
        },
        "cliente": (conteudo.get("cliente") or {}).get("nome") or "Cliente do site",
        # o pedido do site é da CONTA do site, e não de um cadastro de Clientes
        "cliente_id": None,
        "papel": papel_curto(conteudo),
        "situacao": "assinado" if documento.assinado else ("suspenso" if suspenso else "aguardando"),
        "url_via": via,
        "url_imprimir": f"{via}&imprimir=1",
        "url_pagina": "",
        "pode_qr": False,
    }


class ViaDoContratoDoPedidoView(InternoRequiredMixin, View):
    """A via (para ver, imprimir ou salvar em PDF) do contrato de um pedido do site.

    Só leitura, para quem vê os pedidos do site (`assinaturas_pedidos`:
    Financeiro e Gestão) -- também por URL direta (403).
    """

    funcoes_necessarias = (FINANCEIRO, GESTAO)

    def get(self, request, pk):
        from django.core.exceptions import PermissionDenied
        from django.shortcuts import get_object_or_404

        from core.views_assinatura import contexto_da_folha

        if not capacidades(request.user)["assinaturas_pedidos"]:
            raise PermissionDenied("O contrato do pedido do site é de quem vê os pedidos do site.")
        documentos = DocumentoAssinatura.objects.filter(pedido_id=pk).exclude(
            situacao=DocumentoAssinatura.Situacao.SUBSTITUIDO,
        )
        escolhido = request.GET.get("documento", "")
        if escolhido.isdigit():
            documento = get_object_or_404(DocumentoAssinatura, pk=int(escolhido), pedido_id=pk)
        else:
            documento = get_object_or_404(documentos.order_by("-id")[:1])
        contexto = contexto_da_folha(documento, painel=True)
        contexto["voltar_url"] = reverse("assinaturas_inner", urlconf=URLCONF) + "?objeto=pedidos"
        contexto["imprimir_ao_abrir"] = request.GET.get("imprimir") == "1"
        resposta = render(request, "assinatura_via.html", contexto)
        resposta["Cache-Control"] = "no-store"
        resposta["X-LS-No-Store"] = "1"
        return resposta


class AssinaturasInnerView(InternoRequiredMixin, View):
    """A lista das assinaturas, em cards, por objeto."""

    template_name = "assinaturas_inner.html"
    funcoes_necessarias = (VENDAS, AMBULANTE, FINANCEIRO, GESTAO, PRODUCAO)
    #: Múltiplo de 12: com 1, 2, 3 ou 4 cards por fileira, a última fileira
    #: de uma página que continua nunca sai pela metade.
    POR_PAGINA = 24

    def get(self, request):
        acesso = capacidades(request.user)
        if not acesso["assinaturas"]:
            return redirect(self.destino_do_usuario(request.user))

        visiveis = documentos_visiveis(request.user)
        # os objetos que ESTA pessoa vê: o chip de objeto só existe com mais de um
        objetos_que_ve = [chave for chave, capacidade in CAPACIDADE_DO_OBJETO.items() if acesso[capacidade]]
        ve_os_dois = len(objetos_que_ve) > 1

        situacao = (request.GET.get("situacao") or "todas").strip()
        if situacao not in {valor for valor, _, _ in SITUACOES}:
            situacao = "todas"
        objeto = (request.GET.get("objeto") or "todos").strip()
        if not ve_os_dois or objeto not in objetos_que_ve:
            objeto = "todos"
        busca = (request.GET.get("q") or "").strip()[:80]

        # AS ASSINATURAS DE UM CLIENTE (seção 144): a tela Clientes chega
        # aqui com ?cliente=<id>. O filtro é pelo vínculo de verdade e só
        # corta o que a pessoa JÁ podia ver -- o id de um cliente alheio
        # devolve a lista vazia, sem dizer nem o nome dele.
        cliente_id = (request.GET.get("cliente") or "").strip()
        cliente_id = int(cliente_id) if cliente_id.isdigit() and len(cliente_id) < 10 else None
        if cliente_id:
            visiveis = visiveis.filter(do_cliente(cliente_id))

        do_objeto = {"orcamentos": _DO_ORCAMENTO, "os": _DA_ORDEM, "pedidos": _DO_PEDIDO}.get(objeto, Q())
        da_situacao = {
            "assinadas": Q(situacao=ASSINADO), "aguardando": Q(situacao=AGUARDANDO),
        }.get(situacao, Q())
        da_busca = Q()
        if busca:
            da_busca = (
                Q(orcamento__nome_cliente__icontains=busca)
                | Q(ordem_servico__nome_cliente__icontains=busca)
                | Q(assinante_nome__icontains=busca)
                | (_DO_PEDIDO & Q(conteudo__cliente__nome__icontains=busca))
            )
            numero = _numero_buscado(busca)
            if numero:
                da_busca |= Q(orcamento_id=numero) | (_DA_ORDEM & Q(ordem_servico_id=numero)) | Q(pedido_id=numero)

        # Os números dos chips, numa consulta só: cada chip conta o que ele
        # mostraria com a busca e com o OUTRO filtro como estão.
        com_busca = visiveis.filter(da_busca)
        numeros = com_busca.aggregate(
            todas=Count("pk", filter=do_objeto),
            assinadas=Count("pk", filter=do_objeto & Q(situacao=ASSINADO)),
            aguardando=Count("pk", filter=do_objeto & Q(situacao=AGUARDANDO)),
            todos=Count("pk", filter=da_situacao),
            orcamentos=Count("pk", filter=da_situacao & _DO_ORCAMENTO),
            os=Count("pk", filter=da_situacao & _DA_ORDEM),
            pedidos=Count("pk", filter=da_situacao & _DO_PEDIDO),
        )

        lista = (
            com_busca.filter(do_objeto, da_situacao)
            .select_related("orcamento", "ordem_servico", "pedido")
            # o traço (PNG) e o diário não aparecem no card: não viajam
            .defer("assinatura_png", "diario", "assinatura_navegador")
            .annotate(quando=Coalesce("assinado_em", "criacao"))
            .order_by("-quando", "-id")
        )
        paginador = Paginator(lista, self.POR_PAGINA)
        # o chip aceso já contou exatamente esta lista: a página não conta de novo
        paginador.count = numeros[situacao]
        pagina = paginador.get_page(request.GET.get("page"))

        def endereco(**troca):
            atual = {"situacao": situacao, "objeto": objeto, "q": busca, "cliente": str(cliente_id or "")}
            atual.update(troca)
            padrao = {"situacao": "todas", "objeto": "todos", "q": "", "cliente": ""}
            partes = {chave: valor for chave, valor in atual.items() if valor != padrao[chave]}
            return "?" + urlencode(partes) if partes else reverse("assinaturas_inner", urlconf=URLCONF)

        # O nome no chip "Cliente: ..." só aparece para quem vê o cadastro
        # (o Comercial) ou tem pelo menos um documento dele na tela.
        cliente_nome = ""
        if cliente_id and (acesso["clientes"] or numeros["todos"] or numeros["todas"]):
            cliente_nome = (
                Cliente.objects.filter(pk=cliente_id).values_list("nome_cliente", flat=True).first() or ""
            )

        return render(request, self.template_name, {
            "cliente_id": cliente_id,
            "cliente_nome": cliente_nome,
            "url_sem_cliente": endereco(cliente=""),
            "pode_ver_clientes": acesso["clientes"],
            "url_clientes": reverse("clientes_inner", urlconf=URLCONF),
            "cartoes": [_cartao(documento, acesso) for documento in pagina.object_list],
            "pagina": pagina,
            "total": pagina.paginator.count,
            "situacao": situacao,
            "objeto": objeto,
            "busca": busca,
            "ve_os_dois": ve_os_dois,
            # O texto do topo só fala em "abrir o QR" a quem tem o QR de algum
            # objeto que vê (seção 140): quem só lê, imprime e acompanha.
            "pode_algum_qr": (
                (acesso["assinaturas_orcamentos"] and acesso["orcamentos_editar_comercial"])
                or (acesso["assinaturas_os"] and acesso["ordens_servico_editar"])
            ),
            "so_orcamentos": objetos_que_ve == ["orcamentos"],
            "so_os": objetos_que_ve == ["os"],
            "ve_pedidos": acesso["assinaturas_pedidos"],
            "carteira_propria": acesso["assinaturas_orcamentos"] and acesso["orcamentos_proprios"],
            "chips_situacao": [
                {"valor": valor, "rotulo": rotulo, "icone": icone, "ativo": valor == situacao,
                 "quantos": numeros[valor], "url": endereco(situacao=valor)}
                for valor, rotulo, icone in SITUACOES
            ],
            "chips_objeto": [
                {"valor": valor, "rotulo": rotulo, "icone": icone, "ativo": valor == objeto,
                 "quantos": numeros[valor], "url": endereco(objeto=valor)}
                for valor, rotulo, icone in OBJETOS
                if valor == "todos" or valor in objetos_que_ve
            ] if ve_os_dois else [],
            "url_limpar": endereco(q=""),
            "url_pagina": endereco() + ("&" if "?" in endereco() else "?"),
            "validade_texto": svc.prazo_do_link(),
        })
