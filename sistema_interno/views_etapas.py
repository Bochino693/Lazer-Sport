"""A régua do pedido, pronta, para a janela do orçamento (LEIA-ME-V10, seção 117).

A janela abre o orçamento com os dados da lista e pede aqui a régua: as seis
fases e o próximo passo, em HTML já desenhado (`partes/etapas_do_pedido.html`
-- a mesma parte da tela do contrato). Uma regra, um desenho, duas telas.
"""

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.views.generic import View

from .etapas_do_pedido import etapas
from .models import Orcamento
from .permissoes import limitar_orcamentos
from .views import OrcamentoInternoRequiredMixin


class EtapasDoOrcamentoView(OrcamentoInternoRequiredMixin, View):
    """GET: {"marca", "html"} -- só o HTML quando a marca mudou (`?marca=`)."""

    def get(self, request, pk):
        # A O.S. e a produção (as duas do outro lado de um um-para-um) no
        # mesmo SELECT, e os itens numa consulta só: a régua lia os itens três
        # vezes (o total, o pagamento, a produção) -- cada leitura uma viagem
        # ao Supabase (~170 ms, LEIA-ME-V10 §120), e esta rota é pedida a
        # cada janela de orçamento aberta.
        orcamento = get_object_or_404(
            limitar_orcamentos(
                request.user,
                Orcamento.objects.select_related("cliente", "ordem_servico", "producao")
                .prefetch_related("itens"),
            ),
            pk=pk,
        )
        regua = etapas(orcamento, request.user)
        corpo = {"status": "sucesso", "marca": regua.marca, "feitas": regua.feitas}
        if request.GET.get("marca", "") != regua.marca:
            corpo["html"] = render_to_string(
                "partes/etapas_do_pedido.html", {"etapas": regua, "na_janela": True}, request=request,
            )
        resposta = JsonResponse(corpo)
        resposta["Cache-Control"] = "no-store"
        return resposta
