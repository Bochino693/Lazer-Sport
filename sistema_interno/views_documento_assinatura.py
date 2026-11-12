"""As telas do painel para o documento de assinatura do orçamento pago.

A regra de negócio mora em `documento_assinatura.py`; aqui fica só o que o
painel mostra e o que ele pede:

  * a tela do documento (o cartão com o QR, o relógio de 5 minutos, o link,
    o WhatsApp e, depois, o "Assinado por ..." com o PDF);
  * gerar (e gerar de novo, enquanto ninguém assinou);
  * um link novo -- o cartão pede sozinho a cada 5 minutos, e no botão;
  * o estado, que o cartão consulta a cada 10 segundos enquanto está aberto;
  * a via para imprimir ou salvar em PDF.

QUEM PODE. A mesma permissão de editar o orçamento no bloco comercial
(`orcamentos_editar_comercial`: Vendas, Ambulante e Gestão), que é a de
enviar a proposta ao cliente -- mandar o termo para assinar é o mesmo
gesto. E a mesma carteira: o Ambulante só vê os orçamentos dele
(`limitar_orcamentos`), inclusive por URL direta.
"""

from __future__ import annotations

from urllib.parse import quote

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.generic import View

from . import documento_assinatura as svc
from .context_processors import invalidar_avisos
from .models import DocumentoAssinatura, Orcamento
from .permissoes import capacidades, limitar_orcamentos
from .utils import ErroDeFormulario, endereco_do_site, pede_json
from .validacoes import mascarar_documento
from .views import OrcamentoInternoRequiredMixin

URLCONF = "sistema_interno.urls"


def pode_documento(user) -> bool:
    """Quem gera, renova e acompanha o documento de assinatura."""
    return capacidades(user)["orcamentos_editar_comercial"]


def _sem_cache(resposta):
    """O cartão nunca vem do cache: um QR guardado seria um link vencido.

    A navegação do painel guarda as telas que visitou e antecipa as que o
    dedo encosta (ls-soft-navigation.js). `no-store` tira esta tela dos
    dois -- e o link em si nem vem no HTML: o cartão o pede ao abrir.
    """
    resposta["Cache-Control"] = "no-store"
    resposta["X-LS-No-Store"] = "1"
    return resposta


def situacao_do_cartao(orcamento, documento) -> str:
    """A cara do cartão, numa palavra -- a mesma na tela e no estado.

    O cartão aberto compara a dele com a do servidor a cada 10 segundos; se
    mudar (assinou, alguém gerou de novo, o pagamento mudou), troca.
    """
    if documento is None:
        return "gerar" if orcamento.quitado else "bloqueado"
    if not documento.assinado and not orcamento.quitado:
        return "suspenso"
    return documento.situacao


def _conversa_whatsapp(telefone, mensagem):
    from .views_gestao import OrcamentosInnerView

    return OrcamentosInnerView.conversa_whatsapp(telefone, mensagem)


class _BaseDocumento(OrcamentoInternoRequiredMixin, View):
    def orcamento(self, request, pk):
        if not pode_documento(request.user):
            raise PermissionDenied(
                "O documento de assinatura pertence a quem edita o orçamento (Comercial)."
            )
        return get_object_or_404(
            limitar_orcamentos(
                request.user,
                Orcamento.objects.select_related("cliente", "responsavel"),
            ),
            pk=pk,
        )

    @staticmethod
    def urls(orcamento):
        return {
            "pagina": reverse("documento_assinatura_inner", args=[orcamento.pk], urlconf=URLCONF),
            "link": reverse("documento_assinatura_link", args=[orcamento.pk], urlconf=URLCONF),
            "estado": reverse("documento_assinatura_estado", args=[orcamento.pk], urlconf=URLCONF),
            "via": reverse("documento_assinatura_via", args=[orcamento.pk], urlconf=URLCONF),
            "lista": reverse("orcamentos_inner", urlconf=URLCONF),
        }

    def contexto_cartao(self, request, orcamento, documento):
        conteudo = (documento.conteudo if documento else None) or {}
        return {
            "orcamento": orcamento,
            "documento": documento,
            "situacao_cartao": situacao_do_cartao(orcamento, documento),
            "conteudo": conteudo,
            "urls": self.urls(orcamento),
            "validade_minutos": svc.VALIDADE_DO_LINK // 60,
            "validade_segundos": svc.VALIDADE_DO_LINK,
            "whatsapp_cliente": orcamento.whatsapp_destinatario,
            "assinatura_img": svc.assinatura_data_url(documento) if documento else "",
            "documento_assinante": (
                mascarar_documento(documento.assinante_documento)
                if documento and documento.assinante_documento else ""
            ),
            # Sem documento, o resumo mostra o orçamento de agora.
            "itens": [] if documento else list(orcamento.itens.all()),
        }

    def partes_html(self, request, orcamento, documento):
        """O cartão e o resumo, renderizados para o JSON trocar na tela."""
        contexto = self.contexto_cartao(request, orcamento, documento)
        return {
            "html": render_to_string("documento_assinatura/cartao.html", contexto, request=request),
            "resumo": render_to_string("documento_assinatura/resumo.html", contexto, request=request),
        }


class DocumentoAssinaturaInnerView(_BaseDocumento):
    """A tela do documento: o cartão, e o "Gerar" (POST)."""

    def get(self, request, pk):
        orcamento = self.orcamento(request, pk)
        documento = svc.documento_atual(orcamento)
        contexto = self.contexto_cartao(request, orcamento, documento)
        return _sem_cache(render(request, "documento_assinatura_inner.html", contexto))

    def post(self, request, pk):
        orcamento = self.orcamento(request, pk)
        if request.POST.get("action") != "gerar":
            return JsonResponse({"status": "erro", "msg": "Ação inválida."}, status=400)
        try:
            documento = svc.gerar(orcamento, request.user)
        except ErroDeFormulario as erro:
            if pede_json(request):
                return JsonResponse({"status": "erro", "msg": str(erro)}, status=409)
            return redirect(self.urls(orcamento)["pagina"])
        invalidar_avisos(request.user)
        orcamento.refresh_from_db()
        if pede_json(request):
            return JsonResponse({
                "status": "sucesso",
                "msg": "Documento gerado. O link de assinatura já está valendo.",
                "documento": documento.pk,
                **self.partes_html(request, orcamento, documento),
            })
        return redirect(self.urls(orcamento)["pagina"])


class LinkDocumentoAssinaturaView(_BaseDocumento):
    """Um link novo de 5 minutos, com o QR e a conversa do WhatsApp prontos."""

    def get(self, request, pk):
        # Gerar link conta no histórico do documento: só por POST.
        return JsonResponse({"status": "erro", "msg": "Use POST."}, status=405)

    def post(self, request, pk):
        orcamento = self.orcamento(request, pk)
        documento = svc.documento_atual(orcamento)
        if documento is None or not documento.aguardando:
            return JsonResponse({
                "status": "erro",
                "msg": (
                    "Este documento já foi assinado." if documento and documento.assinado
                    else "Gere o documento antes de pedir o link."
                ),
                "situacao": documento.situacao if documento else "",
            }, status=409)

        if not orcamento.quitado:
            return JsonResponse({
                "status": "erro",
                "msg": (
                    "O orçamento não está mais pago: o documento diz que está. "
                    "Acerte o pagamento ou gere o documento de novo."
                ),
                "situacao": "suspenso",
            }, status=409)

        token, expira_em = svc.emitir_link(documento)
        caminho = reverse("documento_assinatura_publico", args=[token], urlconf=settings.ROOT_URLCONF)
        link = f"{endereco_do_site(request)}{caminho}"
        mensagem = svc.mensagem_whatsapp(documento, link)
        return JsonResponse({
            "status": "sucesso",
            "documento": documento.pk,
            "link": link,
            "qr": svc.qr_svg(link),
            # Milissegundos, como o relógio do navegador conta. O cartão
            # desconta a diferença entre o relógio dele e o do servidor.
            "expira_em": expira_em * 1000,
            "agora": int(timezone.now().timestamp() * 1000),
            "validade": svc.VALIDADE_DO_LINK,
            "numero": documento.links_gerados,
            "mensagem": mensagem,
            "whatsapp": _conversa_whatsapp(orcamento.whatsapp_destinatario, mensagem),
            "whatsapp_sem_numero": f"https://wa.me/?text={quote(mensagem, safe='')}",
        })


class EstadoDocumentoAssinaturaView(_BaseDocumento):
    """O que o cartão pergunta a cada 10 segundos: já assinou?

    Leve de propósito: uma consulta. O HTML do cartão só vem quando muda
    (documento outro, ou outra situação), e é ele que troca o QR pelo
    "Assinado por ..." sem recarregar a tela.
    """

    def get(self, request, pk):
        orcamento = self.orcamento(request, pk)
        documento = svc.documento_atual(orcamento)
        corpo = {
            "status": "sucesso",
            "documento": documento.pk if documento else None,
            "situacao": situacao_do_cartao(orcamento, documento),
            "assinado": bool(documento and documento.assinado),
        }
        visto_doc = request.GET.get("documento", "")
        visto_situacao = request.GET.get("situacao", "")
        mudou = (
            str(corpo["documento"] or "") != visto_doc
            or corpo["situacao"] != visto_situacao
        )
        corpo["mudou"] = mudou
        if mudou:
            corpo.update(self.partes_html(request, orcamento, documento))
            if documento and documento.assinado:
                corpo["msg"] = (
                    f"{documento.assinante_nome} assinou o documento do orçamento "
                    f"#{orcamento.pk}."
                )
        resposta = JsonResponse(corpo)
        resposta["Cache-Control"] = "no-store"
        return resposta


class ViaDocumentoAssinaturaInnerView(_BaseDocumento):
    """A via para imprimir ou salvar em PDF, vista de dentro do painel.

    O projeto não tem biblioteca de PDF (nem weasyprint, nem reportlab):
    a via é uma página pronta para a impressão do navegador, com o botão
    "Salvar em PDF" -- o mesmo caminho da proposta ("Imprimir ou salvar em
    PDF"). Com `?imprimir=1` a janela de impressão abre sozinha: é o
    "Baixar PDF" do cartão.
    """

    def get(self, request, pk):
        orcamento = self.orcamento(request, pk)
        escolhido = request.GET.get("documento", "")
        if escolhido.isdigit():
            documento = get_object_or_404(
                DocumentoAssinatura, pk=int(escolhido), orcamento=orcamento,
            )
        else:
            documento = svc.documento_atual(orcamento)
        if documento is None:
            return redirect(self.urls(orcamento)["pagina"])

        from core.views_assinatura import contexto_da_folha

        contexto = contexto_da_folha(documento, painel=True)
        contexto["voltar_url"] = self.urls(orcamento)["pagina"]
        contexto["imprimir_ao_abrir"] = request.GET.get("imprimir") == "1"
        return _sem_cache(render(request, "assinatura_via.html", contexto))
