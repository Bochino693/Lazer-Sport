"""O comprovante de venda que o CLIENTE abre e assina.

Mora no `core`, e não no `sistema_interno`, pelo mesmo motivo da proposta
e da O.S.: o painel responde em interno.lazersport.com.br, atrás do login
da equipe, e uma página hospedada lá seria inalcançável para o cliente.

O QUE ESTE DOCUMENTO É. Uma proposta aprovada pode ser paga em pedaços --
entrada agora, o resto na entrega. Cada pedaço recebido é uma venda (ver
`sistema_interno/vendas.py`), e esta página é o comprovante daquele
pedaço: o que foi comprado, quanto custa o total, quanto foi pago, quanto
falta -- e a assinatura eletrônica de quem pagou.

O QUE SUSTENTA A ASSINATURA SEM SENHA:

  * o token tem ~190 bits de aleatoriedade, então não se chega ao
    comprovante de um cliente adivinhando o de outro;
  * assina-se uma vez. Assinado, o mesmo link vira recibo e para de
    aceitar mudança;
  * o conteúdo assinado é congelado num hash (ver `assinaturas.py`): se o
    documento mudar depois, a conferência acusa;
  * a página não expõe nada além desta venda -- sem histórico do cliente,
    sem link para o painel.
"""

import logging

from django.conf import settings
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from django.views.generic import View

from core.email_utils import cnpj_empresa, nome_empresa
from core.models import EnderecoEmpresa
from sistema_interno.assinaturas import criar_aceite_venda, documento_mascarado
from sistema_interno.models import Venda
from sistema_interno.validacoes import documento_valido, tipo_documento

log = logging.getLogger(__name__)


def carregar_venda(*, bloquear=False, **filtros):
    consulta = (
        Venda.objects
        .select_related(
            "orcamento", "ordem_servico", "cliente", "aceite_eletronico",
        )
        .prefetch_related("orcamento__itens", "ordem_servico__itens")
    )
    if bloquear:
        consulta = consulta.select_for_update()
    return get_object_or_404(consulta, **filtros)


def contexto_venda(venda, *, previsualizacao=False, request=None):
    empresa = EnderecoEmpresa.objects.filter(ativo=True).first()
    documento = venda.documento_de_origem
    aceite = getattr(venda, "aceite_eletronico", None)

    saldo = venda.valor_documento - venda.valor
    if saldo < 0:
        saldo = saldo.__class__("0.00")

    return {
        "venda": venda,
        "documento": documento,
        "itens": venda.itens_do_documento,
        "saldo": saldo,
        "aceite": aceite,
        "documento_assinante": documento_mascarado(aceite),
        "previsualizacao": previsualizacao,
        # Prévia interna não assina: quem abre ali é a equipe conferindo o
        # papel, e uma assinatura da equipe no lugar da do cliente seria
        # exatamente o que este documento existe para não deixar acontecer.
        "pode_assinar": bool(
            not previsualizacao
            and venda.documento_emitido
            and not aceite
            and venda.situacao != Venda.Situacao.CANCELADA
        ),
        "empresa": empresa,
        "empresa_nome": nome_empresa(),
        "empresa_cnpj": cnpj_empresa(),
        "telefone_empresa": (
            getattr(settings, "EMPRESA_TELEFONE", "")
            or (empresa.telefone if empresa else "")
        ),
        "email_empresa": getattr(settings, "EMPRESA_EMAIL", ""),
        "instagram_empresa": getattr(settings, "EMPRESA_INSTAGRAM", ""),
    }


class VendaPublicaView(View):
    """Mostra o comprovante e recebe a assinatura do cliente."""

    template_name = "venda_publica.html"

    def get(self, request, token):
        venda = carregar_venda(token=token)
        if not venda.documento_emitido:
            # 404 e não 403: para quem tem o link, o documento simplesmente
            # ainda não existe -- a equipe não o emitiu.
            raise Http404("Comprovante ainda não emitido.")
        return render(
            request,
            self.template_name,
            contexto_venda(venda, request=request),
        )

    def post(self, request, token):
        with transaction.atomic():
            # Trava só esta venda: duas abas podem clicar juntas, e apenas
            # a primeira assina; a outra reencontra o recibo pronto.
            venda = carregar_venda(token=token, bloquear=True)
            contexto = contexto_venda(venda, request=request)

            if not contexto["pode_assinar"]:
                return redirect("venda_publica", token=token)

            nome = (request.POST.get("nome") or "").strip()
            documento_informado = (
                request.POST.get("documento_assinante") or ""
            ).strip()
            consentiu = (request.POST.get("consentimento") or "") in ("1", "on")

            contexto["nome_tentado"] = nome
            contexto["documento_tentado"] = documento_informado
            contexto["consentimento_tentado"] = consentiu

            if not nome:
                contexto["erro"] = "Escreva seu nome para assinar o comprovante."
                return render(request, self.template_name, contexto, status=400)

            if not documento_valido(documento_informado):
                contexto["erro"] = (
                    f"{tipo_documento(documento_informado).capitalize()} inválido. "
                    "Confira os caracteres e os dígitos verificadores."
                )
                return render(request, self.template_name, contexto, status=400)

            if not consentiu:
                contexto["erro"] = "Marque a confirmação para assinar eletronicamente."
                return render(request, self.template_name, contexto, status=400)

            criar_aceite_venda(
                venda,
                request,
                nome=nome,
                documento=documento_informado,
            )
            venda.marcar_assinada()

        # O aviso à equipe nunca pode virar erro para o cliente: a
        # assinatura já está gravada quando chegamos aqui.
        try:
            from sistema_interno.notificacoes import avisar_venda_assinada

            avisar_venda_assinada(venda)
        except Exception:
            log.exception(
                "Não consegui avisar a equipe sobre a assinatura da venda %s",
                venda.pk,
            )

        # Redireciona em vez de renderizar: atualizar a página reenviaria o
        # formulário de um documento já assinado.
        return redirect("venda_publica", token=token)


venda_publica = require_http_methods(["GET", "POST"])(VendaPublicaView.as_view())
