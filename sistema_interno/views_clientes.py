"""Aba de clientes do painel interno.

POR QUE ESTA TELA EXISTE. O cliente aparecia no sistema só como um nome
digitado dentro de um orçamento. Quem ligava pela segunda vez virava um
cadastro novo, o histórico nascia partido e não havia como responder duas
perguntas simples: quanto este cliente já fechou, e quais clientes vieram
por qual buffet.

O buffet é cliente também -- aluga brinquedo, pede peça, chama
manutenção --, então mora na mesma lista, marcado como parceiro. O que os
liga é `Cliente.parceiro`.
"""

from __future__ import annotations

from decimal import Decimal

from django.core.paginator import Paginator
from django.db.models import Count, Prefetch, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.generic import View

from core.models import Clientes as ClienteMapa, Estabelecimentos

from . import clientes as svc
from .models import Cliente, EnderecoCliente, Orcamento
from .utils import ErroDeFormulario
from .views import GestorInternoRequiredMixin, RespostaJSONMixin


ZERO = Decimal("0.00")


class ClientesInnerView(RespostaJSONMixin, GestorInternoRequiredMixin, View):
    """Lista, cadastra e liga clientes a buffets parceiros."""

    rota_padrao = "clientes_inner"
    template_name = "clientes_inner.html"
    POR_PAGINA = 30

    # ------------------------------------------------------------ leitura
    def get(self, request):
        busca = (request.GET.get("q") or "").strip()
        tipo = (request.GET.get("tipo") or "").strip()
        parceiro = (request.GET.get("parceiro") or "").strip()

        consulta = (
            Cliente.objects
            .select_related("parceiro", "estabelecimento", "cliente_mapa")
            .prefetch_related(
                Prefetch(
                    "enderecos",
                    queryset=EnderecoCliente.objects.order_by("id"),
                ),
                Prefetch(
                    "orcamentos",
                    queryset=Orcamento.objects.prefetch_related("itens"),
                ),
            )
            .annotate(
                clientes_do_buffet=Count("clientes_atendidos", distinct=True),
            )
            .order_by("nome_cliente", "id")
        )

        consulta = svc.buscar(consulta, busca)

        if tipo in Cliente.Tipo.values:
            consulta = consulta.filter(tipo=tipo)

        if parceiro.isdigit():
            consulta = consulta.filter(parceiro_id=int(parceiro))

        pagina = Paginator(consulta, self.POR_PAGINA).get_page(
            request.GET.get("page")
        )

        # A lista vira list() para os totais calculados abaixo não se
        # perderem quando o template percorrer a página de novo.
        pagina.object_list = list(pagina.object_list)
        fichas = [self.ficha(cliente) for cliente in pagina.object_list]

        todos = Cliente.objects.all()
        buffets = list(
            todos.filter(tipo=Cliente.Tipo.BUFFET).order_by("nome_cliente")
        )
        totais = todos.aggregate(
            clientes=Count("id"),
            buffets=Count("id", filter=Q(tipo=Cliente.Tipo.BUFFET)),
            vinculados=Count("id", filter=Q(parceiro__isnull=False)),
            sem_contato=Count(
                "id",
                filter=(Q(telefone="") | Q(telefone__isnull=True))
                & (Q(email="") | Q(email__isnull=True)),
            ),
        )

        ids_da_pagina = [cliente.pk for cliente in pagina.object_list]
        mapas_disponiveis = (
            ClienteMapa.objects
            .filter(Q(cliente_interno__isnull=True) | Q(cliente_interno__id__in=ids_da_pagina))
            .distinct()
            .order_by("descricao_cliente")
        )
        estabelecimentos_disponiveis = (
            Estabelecimentos.objects
            .filter(Q(clientes_internos__isnull=True) | Q(clientes_internos__id__in=ids_da_pagina))
            .distinct()
            .order_by("nome_estabelecimento")
        )

        contexto = {
            "fichas": fichas,
            "page_obj": pagina,
            "busca": busca,
            "tipo_ativo": tipo,
            "parceiro_ativo": parceiro,
            "tipos": Cliente.Tipo.choices,
            "buffets": buffets,
            "estabelecimentos": estabelecimentos_disponiveis,
            "clientes_mapa": mapas_disponiveis,
            "total_clientes": totais["clientes"],
            "total_buffets": totais["buffets"],
            "total_vinculados": totais["vinculados"],
            "total_sem_contato": totais["sem_contato"],
            "clientes_dados": [self.serializar(c) for c in pagina.object_list],
            "opcoes_buffets": [
                {
                    "valor": str(b.id),
                    "rotulo": b.nome_cliente,
                    "detalhe": b.contato_curto,
                }
                for b in buffets
            ],
            "opcoes_clientes_mapa": [
                {
                    "valor": str(mapa.pk),
                    "rotulo": mapa.descricao_cliente or f"Cliente #{mapa.pk}",
                    "detalhe": " · ".join(
                        parte for parte in (
                            mapa.bairro or "",
                            f"{mapa.cidade}/{mapa.estado}" if mapa.cidade else "",
                        ) if parte
                    ) or "Pino público sem endereço completo",
                    "grupo": "Clientes já publicados no mapa",
                }
                for mapa in mapas_disponiveis
            ],
            "opcoes_estabelecimentos": [
                {
                    "valor": str(estabelecimento.pk),
                    "rotulo": estabelecimento.nome_estabelecimento,
                    "detalhe": "Parceiro exibido no site",
                    "grupo": "Parceiros públicos",
                }
                for estabelecimento in estabelecimentos_disponiveis
            ],
        }

        return render(request, self.template_name, contexto)

    @staticmethod
    def ficha(cliente: Cliente) -> dict:
        """O que a lista mostra de cada cliente, já somado.

        Os orçamentos vêm no prefetch, então a soma acontece em memória:
        uma consulta a mais por cliente encheria a tela de idas ao banco
        justamente na hora em que a lista cresce.
        """
        orcamentos = list(cliente.orcamentos.all())
        aprovados = [
            o for o in orcamentos
            if o.status == Orcamento.Status.APROVADO
        ]
        abertos = [o for o in orcamentos if o.status in Orcamento.EM_ABERTO]

        return {
            "obj": cliente,
            "endereco": cliente.endereco_principal,
            "orcamentos": len(orcamentos),
            "aprovados": len(aprovados),
            "abertos": len(abertos),
            "total_aprovado": sum((o.total for o in aprovados), ZERO),
            "ultimo": max(
                (o.criacao for o in orcamentos if o.criacao),
                default=None,
            ),
        }

    @staticmethod
    def serializar(cliente: Cliente) -> dict:
        """Payload que o modal usa para reabrir um cadastro."""
        endereco = cliente.endereco_principal

        return {
            "id": cliente.id,
            "nome_cliente": cliente.nome_cliente,
            "tipo": cliente.tipo,
            "documento": cliente.documento,
            "telefone": cliente.telefone,
            "email": cliente.email or "",
            "parceiro": str(cliente.parceiro_id or ""),
            "estabelecimento": str(cliente.estabelecimento_id or ""),
            "cliente_mapa": str(cliente.cliente_mapa_id or ""),
            "observacoes": cliente.observacoes,
            "cep": endereco.cep if endereco else "",
            "endereco": endereco.endereco if endereco else "",
            "numero": endereco.numero if endereco else "",
            "bairro": endereco.bairro if endereco else "",
            "cidade": endereco.cidade if endereco else "",
            "estado": endereco.estado if endereco else "",
            "latitude": str(endereco.latitude or "") if endereco else "",
            "longitude": str(endereco.longitude or "") if endereco else "",
            "no_mapa": bool(cliente.cliente_mapa_id),
            "mapa_pronto": bool(
                cliente.cliente_mapa_id
                and cliente.cliente_mapa.latitude
                and cliente.cliente_mapa.longitude
            ),
        }

    # ------------------------------------------------------------- ações
    def acao_save(self, request):
        cliente_id = (request.POST.get("id") or "").strip()
        cliente = (
            get_object_or_404(Cliente, pk=cliente_id) if cliente_id else None
        )

        salvo = svc.salvar_cliente(request, cliente)
        svc.salvar_endereco(request, salvo)
        mapa = None
        if salvo.orcamentos.filter(status=Orcamento.Status.APROVADO).exists():
            mapa = svc.sincronizar_cliente_no_mapa(salvo)

        return self.sucesso(
            request,
            (
                f"Cliente “{salvo.nome_cliente}” salvo e atualizado no mapa."
                if mapa and mapa.latitude and mapa.longitude
                else f"Cliente “{salvo.nome_cliente}” salvo."
            ),
            id=salvo.id,
            cliente=svc.opcao_de_busca(salvo),
            mapa_publicado=bool(mapa and mapa.latitude and mapa.longitude),
        )

    def acao_delete(self, request):
        cliente = get_object_or_404(Cliente, pk=request.POST.get("id"))

        # Apagar levaria junto o vínculo dos orçamentos (SET_NULL) e o
        # histórico do cliente sumiria da proposta já enviada.
        if cliente.orcamentos.exists():
            raise ErroDeFormulario(
                f"“{cliente.nome_cliente}” tem orçamento no histórico e não "
                "pode ser excluído. Corrija o cadastro em vez de apagar."
            )

        if cliente.clientes_atendidos.exists():
            raise ErroDeFormulario(
                f"“{cliente.nome_cliente}” é o buffet responsável por outros "
                "clientes. Troque o buffet deles antes de excluir."
            )

        nome = cliente.nome_cliente
        cliente.delete()
        return self.sucesso(request, f"Cliente “{nome}” excluído.")


class ConsultaCepInnerView(GestorInternoRequiredMixin, View):
    """Uma rota interna para todos os formulários reaproveitarem o CEP."""

    def get(self, request):
        try:
            dados = svc.consultar_cep(request.GET.get("cep") or "")
        except ErroDeFormulario as exc:
            return JsonResponse({"status": "erro", "msg": str(exc)}, status=400)

        return JsonResponse({"status": "sucesso", "endereco": dados})
