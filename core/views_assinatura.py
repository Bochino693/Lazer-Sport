"""A página em que o CLIENTE assina, no telefone dele, o termo de compra.

Mora no `core` pelo mesmo motivo da proposta (ver `views_orcamento.py`): o
painel responde em interno.lazersport.com.br, atrás de login de equipe, e
o cliente não tem login. Aqui a página sai no site, aberta, e quem abre a
porta é o link de 5 minutos gerado pelo painel.

O QUE SUSTENTA ISSO (o resto está em `sistema_interno/documento_assinatura.py`):

  * o link é um `TimestampSigner` com sal próprio, preso ao id e ao hash do
    documento: não se fabrica, não se aproveita de outro documento e morre
    em 5 minutos -- conferido ao ABRIR e de novo ao ENVIAR;
  * a página mostra o documento daquele link e mais nada: nenhum outro
    orçamento, nenhum id de cadastro, nenhum caminho para o painel;
  * o envio leva o CSRF do Django, passa por um freio curto por IP e trava
    a linha do documento: duas abas assinando juntas, só a primeira grava;
  * assinado, o documento não se assina de novo -- o link vira o
    comprovante, com a cópia para baixar.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.db import transaction
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from core.registro_cadastro import ip_da_requisicao
from sistema_interno import documento_assinatura as svc
from sistema_interno.models import DocumentoAssinatura
from sistema_interno.validacoes import mascarar_documento

log = logging.getLogger(__name__)


def _cabecalhos(resposta):
    """Página de link pessoal: fora do cache, fora do Google, sem vazar o link.

    `Referrer-Policy` porque o token está no endereço: um clique para fora
    (o WhatsApp da empresa) não pode levar o link junto no cabeçalho.
    """
    resposta["Cache-Control"] = "no-store"
    resposta["X-Robots-Tag"] = "noindex, nofollow"
    resposta["Referrer-Policy"] = "no-referrer"
    return resposta


def _contato_empresa():
    return {
        "whatsapp_empresa": getattr(settings, "ORCAMENTO_WHATSAPP", ""),
        "telefone_empresa": getattr(settings, "ORCAMENTO_TELEFONE", ""),
    }


def contexto_da_folha(documento, *, painel=False):
    """O que a folha do documento precisa, no painel e no site.

    O CPF/CNPJ do cliente sai inteiro só no painel. Na página do link ele
    aparece mascarado: é justamente o número que o cliente digita para
    assinar, e mostrá-lo inteiro ali transformaria a conferência em cópia.
    """
    conteudo = documento.conteudo or {}
    cliente = conteudo.get("cliente") or {}
    documento_cliente = cliente.get("documento", "")
    return {
        "documento": documento,
        "doc": conteudo,
        "painel": painel,
        "cliente_documento": (
            documento_cliente if painel or not documento_cliente
            else mascarar_documento(documento_cliente)
        ),
        "assinatura_img": svc.assinatura_data_url(documento),
        "assinante_documento": (
            svc.documento_pontuado(documento.assinante_documento) if painel
            else mascarar_documento(documento.assinante_documento)
        ) if documento.assinante_documento else "",
        **_contato_empresa(),
    }


def _tela_de_aviso(request, situacao, documento=None, *, status, mensagem=""):
    """Expirou, foi trocado ou não existe: uma tela de app, e não um erro."""
    numero = ""
    if documento is not None:
        numero = ((documento.conteudo or {}).get("orcamento") or {}).get("numero", "")
    contexto = {
        "estado": situacao,
        "numero": numero,
        "mensagem_extra": mensagem,
        **_contato_empresa(),
    }
    return _cabecalhos(render(request, "assinatura_publica.html", contexto, status=status))


def _resposta_de_envio(request, situacao, documento, *, status, mensagem):
    """O POST que não grava: JSON para o formulário, ou a tela de aviso."""
    if request.headers.get("Accept", "").startswith("application/json"):
        corpo = {"ok": False, "situacao": situacao, "msg": mensagem}
        if situacao == "assinado" and documento is not None:
            corpo["destino"] = reverse("documento_assinado_publico", args=[documento.codigo_publico])
        return _cabecalhos(JsonResponse(corpo, status=status))
    if situacao == "assinado" and documento is not None:
        return redirect("documento_assinado_publico", codigo=documento.codigo_publico)
    return _tela_de_aviso(request, situacao, documento, status=status, mensagem=mensagem)


STATUS_DA_SITUACAO = {"expirado": 410, "substituido": 410, "suspenso": 410, "invalido": 404}


@require_http_methods(["GET", "POST"])
def assinar_documento(request, token):
    if request.method == "POST":
        return _enviar_assinatura(request, token)

    leitura = svc.ler_link(token)
    if leitura.situacao == "assinado":
        return redirect("documento_assinado_publico", codigo=leitura.documento.codigo_publico)
    if not leitura.valido:
        return _tela_de_aviso(
            request, leitura.situacao, leitura.documento,
            status=STATUS_DA_SITUACAO[leitura.situacao],
        )

    contexto = contexto_da_folha(leitura.documento)
    contexto.update({
        "estado": "assinar",
        "token": token,
        # O relógio da página: o instante em que o link morre, em ms. O
        # navegador desconta a diferença do relógio dele (`agora`).
        "expira_em_ms": leitura.expira_em * 1000,
        "segundos_restantes": leitura.segundos_restantes,
        "validade_minutos": svc.VALIDADE_DO_LINK // 60,
    })
    return _cabecalhos(render(request, "assinatura_publica.html", contexto))


def _enviar_assinatura(request, token):
    ip, _ = ip_da_requisicao(request)
    if svc.tentativas_estouradas(ip):
        return _resposta_de_envio(
            request, "limite", None, status=429,
            mensagem="Muitas tentativas seguidas. Espere alguns minutos e tente de novo.",
        )

    with transaction.atomic():
        leitura = svc.ler_link(token, bloquear=True)
        documento = leitura.documento
        if leitura.situacao == "assinado":
            quando = documento.assinado_em
            return _resposta_de_envio(
                request, "assinado", documento, status=409,
                mensagem=(
                    "Este documento já foi assinado"
                    + (f" em {quando:%d/%m/%Y}" if quando else "")
                    + ". Nada foi alterado."
                ),
            )
        if not leitura.valido:
            mensagens = {
                "expirado": "O tempo do link acabou antes do envio. Nada foi salvo: peça um novo link ao atendente.",
                "substituido": "Este link é de uma versão anterior do documento. Nada foi salvo: peça o link novo ao atendente.",
                "suspenso": "Este documento está suspenso: o pagamento do orçamento mudou. Nada foi salvo; fale com o atendente.",
                "invalido": "Link inválido. Nada foi salvo.",
            }
            return _resposta_de_envio(
                request, leitura.situacao, documento,
                status=STATUS_DA_SITUACAO[leitura.situacao],
                mensagem=mensagens[leitura.situacao],
            )

        try:
            nome, cpf_cnpj = svc.conferir_campos(
                documento,
                nome=request.POST.get("nome"),
                cpf_cnpj=request.POST.get("documento"),
                concordo=request.POST.get("concordo") in ("1", "on", "true"),
            )
            png = svc.png_da_assinatura(request.POST.get("assinatura"))
        except svc.AssinaturaRecusada as recusa:
            corpo = {"ok": False, "situacao": "campo", "campo": recusa.campo, "msg": str(recusa)}
            if request.headers.get("Accept", "").startswith("application/json"):
                return _cabecalhos(JsonResponse(corpo, status=400))
            contexto = contexto_da_folha(documento)
            contexto.update({
                "estado": "assinar",
                "token": token,
                "expira_em_ms": leitura.expira_em * 1000,
                "segundos_restantes": leitura.segundos_restantes,
                "validade_minutos": svc.VALIDADE_DO_LINK // 60,
                "erro": str(recusa),
                "erro_campo": recusa.campo,
                "nome_tentado": request.POST.get("nome", "")[:160],
                "documento_tentado": request.POST.get("documento", "")[:20],
            })
            return _cabecalhos(render(request, "assinatura_publica.html", contexto, status=400))

        svc.assinar(
            documento,
            nome=nome,
            cpf_cnpj=cpf_cnpj,
            png=png,
            ip=ip,
            navegador=request.META.get("HTTP_USER_AGENT", ""),
        )

    # O telefone da equipe toca -- e nada disso pode virar erro para o
    # cliente, que acabou de assinar.
    try:
        from sistema_interno.notificacoes import avisar_documento_assinado

        avisar_documento_assinado(documento)
    except Exception:
        log.exception("Não consegui avisar a equipe da assinatura do documento %s", documento.pk)

    destino = reverse("documento_assinado_publico", args=[documento.codigo_publico]) + "?pronto=1"
    if request.headers.get("Accept", "").startswith("application/json"):
        return _cabecalhos(JsonResponse({"ok": True, "destino": destino}))
    return redirect(destino)


@require_http_methods(["GET"])
def documento_assinado(request, codigo):
    """O comprovante: "assinado em ...", a folha com a assinatura e o PDF.

    Só existe para documento assinado. O código é aleatório (UUID4), como o
    token da proposta: é a cópia do cliente, e quem tem o link a abre.
    """
    documento = get_object_or_404(
        DocumentoAssinatura.objects.select_related("orcamento"),
        codigo_publico=codigo,
    )
    if not documento.assinado:
        raise Http404("Documento ainda não assinado.")
    contexto = contexto_da_folha(documento)
    contexto.update({
        "estado": "assinado",
        "acabou_de_assinar": request.GET.get("pronto") == "1",
        "imprimir_ao_abrir": request.GET.get("imprimir") == "1",
    })
    return _cabecalhos(render(request, "assinatura_publica.html", contexto))
