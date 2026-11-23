"""As telas do painel para a ORDEM DE SERVIÇO assinada no celular (LEIA-ME-V10, 124).

O pedido do dono: "também deve emitir contrato ou ordem de serviço,
destinado a manutenções e serviços, para padronizar" -- inclusive das O.S.
sem pagamento recebido.

É o mesmo cartão do contrato de compra e venda (`views_documento_assinatura`):
o QR, o relógio de 10 minutos, o link, o WhatsApp, o "já assinou?" a cada
10 segundos, o diário de bordo, o assinado com o traço e o PDF -- com o
mesmo script (`interno/documento-assinatura.js`) e a mesma folha. Muda a
origem (a O.S., e não o orçamento) e o papel (`documento_servico.py`).

QUEM PODE. Quem edita a O.S. (`ordens_servico_editar`: Produção e Gestão)
gera, renova o link e acompanha -- também por URL direta (403). A VIA (o
PDF) é leitura: abre para quem vê a O.S. (`ordens_servico`, o Financeiro
incluído, que cobra pelo papel assinado), como a prévia de impressão.
"""

from __future__ import annotations

from urllib.parse import quote

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db.models import Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.generic import View

from . import documento_assinatura as svc
from . import documento_servico as servico
from .context_processors import invalidar_avisos
from .models import DadosContrato, DocumentoAssinatura, EnderecoCliente, OrdemServico
from .permissoes import capacidades
from .utils import ErroDeFormulario, endereco_do_site, pede_json
from .validacoes import mascarar_documento
from .views import OrdemServicoInternoRequiredMixin
from .views_documento_assinatura import _sem_cache, marca_do_diario

URLCONF = "sistema_interno.urls"


def pode_documento_os(user) -> bool:
    """Quem gera, renova e acompanha a ordem de serviço para assinatura."""
    return capacidades(user)["ordens_servico_editar"]


def urls_da_ordem(ordem_id) -> dict:
    return {
        "pagina": reverse("assinatura_os_inner", args=[ordem_id], urlconf=URLCONF),
        "link": reverse("assinatura_os_link", args=[ordem_id], urlconf=URLCONF),
        "estado": reverse("assinatura_os_estado", args=[ordem_id], urlconf=URLCONF),
        "via": reverse("assinatura_os_via", args=[ordem_id], urlconf=URLCONF),
        "lista": reverse("ordens_servico_inner", urlconf=URLCONF),
    }


class _BaseDocumentoOS(OrdemServicoInternoRequiredMixin, View):
    #: A via (o PDF) só lê: abre para quem vê a O.S.
    so_leitura = False

    def ordem(self, request, pk):
        acesso = capacidades(request.user)
        if not acesso["ordens_servico"] or (
            not self.so_leitura and not acesso["ordens_servico_editar"]
        ):
            raise PermissionDenied(
                "A ordem de serviço para assinatura pertence a quem edita a O.S. "
                "(Produção ou Gestão)."
            )
        # Tudo o que o cartão, o resumo e o retrato leem, numa conta fixa
        # de consultas (~170 ms cada no ar): os itens e os endereços do
        # cliente vêm de uma vez.
        return get_object_or_404(
            OrdemServico.objects
            .select_related(
                "cliente", "tecnico", "responsavel", "manutencao__usuario__user",
                "orcamento", "ordem_refeita",
            )
            .prefetch_related(
                "itens",
                Prefetch("cliente__enderecos", queryset=EnderecoCliente.objects.order_by("id")),
            ),
            pk=pk,
        )

    @staticmethod
    def urls(ordem):
        return urls_da_ordem(ordem.pk)

    def contexto_cartao(self, request, ordem, documento):
        conteudo = (documento.conteudo if documento else None) or {}
        situacao = servico.situacao_do_cartao_da_ordem(ordem, documento)
        observacoes = []
        condicao = garantia = None
        if documento is None and situacao == "gerar":
            # O que convém saber antes de gerar (nada disso trava), como no
            # contrato de venda: de onde vem a condição de pagamento e o
            # representante em branco.
            total = ordem.total
            condicao, origem = servico.condicao_de_pagamento(
                ordem, total=total, pago=ordem.valor_pago or 0,
                quitado=ordem.quitado, pago_em=ordem.pago_em,
            )
            if origem != "escrita" and total > 0:
                observacoes.append({
                    "chave": "forma",
                    "texto": (
                        "Condição de pagamento (Cláusula 7ª) "
                        f"{servico._ORIGEM_DA_CONDICAO[origem]}: “{condicao}”."
                    ),
                })
            dados = DadosContrato.atual()
            if dados.faltando:
                observacoes.append({
                    "chave": "dados",
                    "texto": (
                        "Os dados do representante ainda estão em branco ("
                        + ", ".join(dados.faltando)
                        + "): o documento sai com “seu representante legal”."
                    ),
                })
            garantia = servico._garantia(ordem.garantia_ate)["rotulo"]
        return {
            "ordem": ordem,
            "documento": documento,
            "conteudo": conteudo,
            "situacao_cartao": situacao,
            "motivo_bloqueio": servico.motivo_para_nao_gerar(ordem) if situacao == "bloqueado" else "",
            "motivo_suspensao": (
                servico.motivo_da_suspensao_da_ordem(documento, ordem)
                if documento is not None and not documento.assinado else ""
            ),
            "observacoes_contrato": observacoes,
            "condicao_previa": condicao,
            "garantia_previa": garantia,
            "pode_dados_contrato": capacidades(request.user)["dados_contrato"],
            "url_dados_contrato": reverse("dados_contrato_inner", urlconf=URLCONF),
            "urls": self.urls(ordem),
            "validade_minutos": svc.VALIDADE_DO_LINK // 60,
            "validade_segundos": svc.VALIDADE_DO_LINK,
            "diario": svc.linhas_do_diario(documento) if documento else [],
            "cliente_com_o_contrato": svc.aberto_agora(documento),
            "marca_do_diario": marca_do_diario(documento),
            "tempo_para_assinar_min": svc.TEMPO_PARA_ASSINAR // 60,
            "whatsapp_cliente": ordem.whatsapp_destinatario,
            "assinatura_img": svc.assinatura_data_url(documento) if documento else "",
            "documento_assinante": (
                mascarar_documento(documento.assinante_documento)
                if documento and documento.assinante_documento else ""
            ),
            # Sem documento, o resumo mostra a O.S. de agora.
            "itens": [] if documento else list(ordem.itens.all()),
        }

    def partes_html(self, request, ordem, documento):
        """O cartão e o resumo, renderizados para o JSON trocar na tela."""
        contexto = self.contexto_cartao(request, ordem, documento)
        return {
            "html": render_to_string("assinatura_os/cartao.html", contexto, request=request),
            "resumo": render_to_string("assinatura_os/resumo.html", contexto, request=request),
        }


class AssinaturaOSInnerView(_BaseDocumentoOS):
    """A tela do documento da O.S.: o cartão, e o "Gerar" (POST)."""

    def get(self, request, pk):
        ordem = self.ordem(request, pk)
        documento = servico.documento_atual_da_ordem(ordem)
        contexto = self.contexto_cartao(request, ordem, documento)
        return _sem_cache(render(request, "assinatura_os_inner.html", contexto))

    def post(self, request, pk):
        ordem = self.ordem(request, pk)
        if request.POST.get("action") != "gerar":
            return JsonResponse({"status": "erro", "msg": "Ação inválida."}, status=400)
        try:
            documento = servico.gerar_da_ordem(ordem, request.user)
        except ErroDeFormulario as erro:
            if pede_json(request):
                return JsonResponse({
                    "status": "erro", "msg": str(erro),
                    "titulo": getattr(erro, "titulo", "") or "A ordem de serviço não saiu",
                }, status=409)
            return redirect(self.urls(ordem)["pagina"])
        invalidar_avisos(request.user)
        if pede_json(request):
            return JsonResponse({
                "status": "sucesso",
                "msg": "Ordem de serviço gerada. O link de assinatura já está valendo.",
                "documento": documento.pk,
                **self.partes_html(request, ordem, documento),
            })
        return redirect(self.urls(ordem)["pagina"])


class LinkAssinaturaOSView(_BaseDocumentoOS):
    """Um link novo de 10 minutos, com o QR e a conversa do WhatsApp prontos."""

    def get(self, request, pk):
        return JsonResponse({"status": "erro", "msg": "Use POST."}, status=405)

    def post(self, request, pk):
        ordem = self.ordem(request, pk)
        documento = servico.documento_atual_da_ordem(ordem)
        if documento is None or not documento.aguardando:
            return JsonResponse({
                "status": "erro",
                "msg": (
                    "Esta ordem de serviço já foi assinada." if documento and documento.assinado
                    else "Gere a ordem de serviço antes de pedir o link."
                ),
                "situacao": documento.situacao if documento else "",
            }, status=409)
        if servico.motivo_da_suspensao_da_ordem(documento, ordem):
            return JsonResponse({
                "status": "erro",
                "msg": (
                    f"A O.S. está como “{ordem.get_status_display().lower()}”: o serviço "
                    "deste documento não vale mais, e nenhum link sai."
                ),
                "situacao": "suspenso",
            }, status=409)

        canal = request.POST.get("canal") if request.POST.get("canal") in ("painel", "whatsapp") else "painel"
        token, expira_em = svc.emitir_link(documento, canal=canal)
        caminho = reverse("documento_assinatura_publico", args=[token], urlconf=settings.ROOT_URLCONF)
        link = f"{endereco_do_site(request)}{caminho}"
        mensagem = svc.mensagem_whatsapp(documento, link)
        from .views_ordens_servico import OrdensServicoInnerView

        return JsonResponse({
            "status": "sucesso",
            "documento": documento.pk,
            "link": link,
            "qr": svc.qr_svg(link),
            "expira_em": expira_em * 1000,
            "agora": int(timezone.now().timestamp() * 1000),
            "validade": svc.VALIDADE_DO_LINK,
            "numero": documento.links_gerados,
            "mensagem": mensagem,
            "whatsapp": OrdensServicoInnerView.conversa_whatsapp(ordem.whatsapp_destinatario, mensagem),
            "whatsapp_sem_numero": f"https://wa.me/?text={quote(mensagem, safe='')}",
        })


class EstadoAssinaturaOSView(_BaseDocumentoOS):
    """O que o cartão pergunta a cada 10 segundos: já assinou?"""

    def get(self, request, pk):
        ordem = self.ordem(request, pk)
        documento = servico.documento_atual_da_ordem(ordem)
        corpo = {
            "status": "sucesso",
            "documento": documento.pk if documento else None,
            "situacao": servico.situacao_do_cartao_da_ordem(ordem, documento),
            "assinado": bool(documento and documento.assinado),
            "diario": marca_do_diario(documento),
        }
        visto_doc = request.GET.get("documento", "")
        mudou = (
            str(corpo["documento"] or "") != visto_doc
            or corpo["situacao"] != request.GET.get("situacao", "")
            or ("diario" in request.GET and request.GET.get("diario", "") != corpo["diario"])
        )
        corpo["mudou"] = mudou
        if mudou:
            corpo.update(self.partes_html(request, ordem, documento))
            if documento and documento.assinado:
                corpo["msg"] = (
                    f"{documento.assinante_nome} assinou a ordem de serviço "
                    f"{ordem.numero_documento}."
                )
        resposta = JsonResponse(corpo)
        resposta["Cache-Control"] = "no-store"
        return resposta


class ViaAssinaturaOSView(_BaseDocumentoOS):
    """A via para imprimir ou salvar em PDF (a mesma folha do link do cliente)."""

    so_leitura = True

    def get(self, request, pk):
        ordem = self.ordem(request, pk)
        escolhido = request.GET.get("documento", "")
        if escolhido.isdigit():
            documento = get_object_or_404(
                DocumentoAssinatura, pk=int(escolhido), ordem_servico=ordem,
            )
        else:
            documento = servico.documento_atual_da_ordem(ordem)
        if documento is None:
            if pode_documento_os(request.user):
                return redirect(self.urls(ordem)["pagina"])
            return redirect(self.urls(ordem)["lista"])

        from core.views_assinatura import contexto_da_folha

        contexto = contexto_da_folha(documento, painel=True)
        contexto["voltar_url"] = (
            self.urls(ordem)["pagina"] if pode_documento_os(request.user)
            else f"{self.urls(ordem)['lista']}?q={ordem.numero_documento}"
        )
        contexto["imprimir_ao_abrir"] = request.GET.get("imprimir") == "1"
        return _sem_cache(render(request, "assinatura_via.html", contexto))
