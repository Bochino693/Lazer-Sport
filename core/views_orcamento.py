"""A página de orçamento que o CLIENTE abre.

Mora no `core`, e não no `sistema_interno`, por um motivo prático: o painel
interno responde em interno.lazersport.com.br, atrás de login de equipe.
Uma página hospedada lá seria inalcançável para o cliente. Aqui ela sai no
site principal, aberta, identificada apenas pelo token do orçamento.

O QUE ISSO SIGNIFICA PARA A SEGURANÇA. Quem tem o link vê a proposta e pode
responder por ela — é o mesmo contrato de um link de rastreio ou de uma
fatura por e-mail, e é o que faz o cliente não precisar de senha. O que
sustenta isso:

  * o token tem 192 bits de aleatoriedade (`gerar_token_orcamento`), então
    não se chega a um orçamento chutando o de outro;
  * a página não expõe nada além da própria proposta — sem cliente, sem
    histórico, sem link para o painel;
  * a resposta é registrada uma única vez. Recebido o "aprovo", o mesmo
    link vira comprovante e para de aceitar mudança;
  * proposta vencida não aceita resposta. Vencimento é regra comercial, e
    quem reabre é a equipe, dando nova validade.
"""

from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.views.generic import View

from sistema_interno.models import Orcamento


def _carregar(token):
    """Busca a proposta pelo token, já com o que a página desenha.

    prefetch dos itens e do brinquedo de cada item: sem isso a página faz
    uma consulta por linha só para mostrar a foto, que é justamente o que
    mais aparece num orçamento grande.
    """
    return get_object_or_404(
        Orcamento.objects
        .select_related("cliente", "responsavel")
        .prefetch_related("itens__brinquedo", "itens__produto"),
        token=token,
    )


def _contexto(orcamento):
    itens = list(orcamento.itens.all())

    return {
        "orcamento": orcamento,
        "itens": itens,
        "quantidade_itens": sum(item.quantidade for item in itens),
        "subtotal": orcamento.subtotal,
        "total": orcamento.total,
        "vencido": orcamento.vencido,
        "respondido": orcamento.respondido,
        "dias_para_vencer": orcamento.dias_para_vencer,
        # A proposta só aceita resposta enquanto está viva: já respondida
        # vira comprovante, vencida precisa de nova validade dada pela
        # equipe. O template usa isto para decidir entre mostrar os botões
        # ou explicar por que eles não estão lá.
        "pode_responder": (
            orcamento.status in Orcamento.EM_ABERTO and not orcamento.vencido
        ),
        "hoje": timezone.localdate(),
    }


class OrcamentoPublicoView(View):
    """Apresenta a proposta e recebe a decisão do cliente."""

    template_name = "orcamento_publico.html"

    def get(self, request, token):
        orcamento = _carregar(token)

        # Rascunho não tem link para ninguém: se a equipe ainda está
        # montando a proposta, o cliente não deveria estar vendo. 404 e não
        # 403 de propósito — para quem tem o link, a página simplesmente
        # ainda não existe.
        if orcamento.status == Orcamento.Status.RASCUNHO:
            raise Http404("Orçamento ainda não enviado.")

        return render(request, self.template_name, _contexto(orcamento))

    def post(self, request, token):
        orcamento = _carregar(token)

        contexto = _contexto(orcamento)
        if not contexto["pode_responder"]:
            # Chegou tarde: alguém respondeu em outra aba, ou a validade
            # passou entre carregar e clicar. Redireciona para a própria
            # página, que já vai explicar a situação.
            return redirect("orcamento_publico", token=token)

        decisao = (request.POST.get("decisao") or "").strip()
        if decisao not in ("aprovar", "recusar"):
            contexto["erro"] = "Escolha aprovar ou recusar a proposta."
            return render(request, self.template_name, contexto, status=400)

        nome = (request.POST.get("nome") or "").strip()
        if not nome:
            contexto["erro"] = "Escreva seu nome para registrar a resposta."
            contexto["decisao_tentada"] = decisao
            return render(request, self.template_name, contexto, status=400)

        orcamento.registrar_resposta(
            aprovado=decisao == "aprovar",
            nome=nome,
            motivo=request.POST.get("motivo") or "",
        )

        # Redireciona em vez de renderizar: sem isso, atualizar a página
        # reenviaria o formulário, e o cliente veria um aviso do navegador
        # perguntando se quer responder de novo a uma proposta já decidida.
        return redirect("orcamento_publico", token=token)


# A view é de classe, mas a rota fica mais legível assim, e é o formato que
# o resto de core/urls.py usa.
orcamento_publico = require_http_methods(["GET", "POST"])(
    OrcamentoPublicoView.as_view()
)
