"""A página do RECIBO — o comprovante que o cliente guarda.

Mora no `core`, e não no `sistema_interno`, pelo mesmo motivo da
proposta: o painel responde em interno.lazersport.com.br, atrás de login
de equipe, e uma página hospedada lá seria inalcançável para quem
pagou. Aqui ela sai no site principal, aberta, identificada apenas pelo
token do recibo.

O QUE ESTA PÁGINA NÃO FAZ. Ela não recebe decisão nenhuma: recibo é
constatação, não negociação. GET e pronto — não há POST para bloquear,
não há estado para mudar, e recarregar mil vezes devolve o mesmo papel.

TOKEN PRÓPRIO, E NÃO O DA PROPOSTA. Quem paga nem sempre é quem
negociou: o recibo vai para o financeiro do buffet, para o setor de
compras, para a prestação de contas. Com o token da proposta junto, o
link do comprovante entregaria também o preço unitário de cada item e a
margem da negociação. São dois documentos, e cada um circula por conta
própria.
"""

from django.conf import settings
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods
from django.views.generic import View

from core.models import EnderecoEmpresa
from core.email_utils import cnpj_empresa, dados_bancarios_empresa, nome_empresa
from sistema_interno.models import ReciboOrcamento
from sistema_interno.recibos import conferir, valor_escrito
from sistema_interno.utils import endereco_do_site


def carregar_recibo(**filtros):
    """Busca o recibo já com o que a página desenha."""
    return get_object_or_404(
        ReciboOrcamento.objects
        .select_related("orcamento", "orcamento__cliente", "emitido_por")
        .prefetch_related("orcamento__itens"),
        **filtros,
    )


def contexto_recibo(recibo, *, request=None):
    """Dados compartilhados pela página pública e pela prévia interna."""
    orcamento = recibo.orcamento
    empresa = EnderecoEmpresa.objects.filter(ativo=True).first()
    base_publica = endereco_do_site(request) if request is not None else ""

    return {
        "recibo": recibo,
        "orcamento": orcamento,
        "itens": list(orcamento.itens.all()),
        # O VALOR POR EXTENSO É PARTE DO DOCUMENTO, não enfeite: é o que
        # impede um "1.500,00" de virar "11.500,00" depois de impresso.
        "valor_escrito": valor_escrito(recibo),
        # Conferido aqui, e não no template: se alguém mexer no banco, a
        # própria página diz que o documento não bate mais com o que foi
        # emitido, em vez de mostrar um recibo alterado com cara de bom.
        "integro": conferir(recibo),
        "empresa": empresa,
        "empresa_nome": nome_empresa(),
        "empresa_cnpj": cnpj_empresa(),
        "dados_bancarios": dados_bancarios_empresa(),
        # O contato do documento é o da EMPRESA, e não o de quem emitiu:
        # dúvida sobre recibo é assunto do escritório. Mesma ordem da
        # proposta -- a configuração da hospedagem manda, o cadastro de
        # endereço só entra se ela estiver vazia.
        "telefone_empresa": (
            getattr(settings, "ORCAMENTO_TELEFONE", "")
            or (empresa.telefone if empresa else "")
        ),
        "whatsapp_empresa": getattr(settings, "ORCAMENTO_WHATSAPP", ""),
        "email_empresa": getattr(settings, "ORCAMENTO_EMAIL", ""),
        "endereco_publico": (
            f"{base_publica}{recibo.caminho_publico}" if base_publica else ""
        ),
    }


class ReciboPublicoView(View):
    """Mostra o recibo. Só isso, e de propósito."""

    template_name = "recibo_pagamento.html"

    def get(self, request, token):
        recibo = carregar_recibo(token=token)
        return render(
            request, self.template_name, contexto_recibo(recibo, request=request)
        )


recibo_publico = require_http_methods(["GET"])(ReciboPublicoView.as_view())
