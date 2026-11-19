"""O termo de exclusividade nas telas: assinar, mandar assinar, a via.

Dois jeitos de assinar, o mesmo quadro e a mesma conferência:

  * NO PAINEL, quem tem conta: a faixa do alto de todas as telas leva a
    "Assinar o termo" (`rh_meu_termo`). A pessoa está logada, então o
    termo é o DELA -- nenhum id viaja no formulário.
  * PELO CELULAR, sem conta: a Gestão abre o termo da pessoa e mostra o QR
    (ou manda o link pelo WhatsApp). O link é o mesmo do termo de compra:
    vale 10 minutos e o cartão pede outro sozinho. A página do link abre
    sem login, mostra só aquele termo e exige o CPF da ficha.
"""

from __future__ import annotations

import logging
from urllib.parse import quote

from django.contrib import messages
from django.db import transaction
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.generic import View

from core.registro_cadastro import ip_da_requisicao
from sistema_interno.permissoes import GESTAO
from sistema_interno.utils import ErroDeFormulario

from . import acesso, termo as svc
from .models import Colaborador, TermoExclusividade
from .validadores import mascarar_cpf
from .views import BaseRH, sem_cache

log = logging.getLogger(__name__)


def _campos_do_post(request):
    return {
        "nome": request.POST.get("nome", ""),
        "cpf": request.POST.get("cpf", ""),
        "concordo": request.POST.get("concordo") in ("1", "on", "true"),
        "assinatura": request.POST.get("assinatura", ""),
    }


def _assinar(request, termo, canal):
    """Confere e grava. Devolve (None, None) ou (mensagem, campo)."""
    campos = _campos_do_post(request)
    try:
        nome, cpf = svc.conferir_campos(termo, nome=campos["nome"], cpf=campos["cpf"], concordo=campos["concordo"])
        png = svc.png_da_assinatura(campos["assinatura"])
    except svc.AssinaturaRecusada as recusa:
        return str(recusa), recusa.campo
    ip, _ = ip_da_requisicao(request)
    svc.assinar(
        termo, nome=nome, cpf=cpf, png=png, ip=ip,
        navegador=request.META.get("HTTP_USER_AGENT", ""), canal=canal, request=request,
    )
    return None, None


def _quer_json(request):
    return request.headers.get("Accept", "").startswith("application/json")


class MeuTermoView(BaseRH):
    """O próprio colaborador lê e assina, no painel."""

    aba = "ficha"

    def termo_para_assinar(self, meu):
        termo = svc.termo_atual(meu)
        if termo is None:
            termo = svc.gerar(meu, None)
        return termo

    def get(self, request, erro="", campo=""):
        meu = self.meu(request)
        if meu is None:
            return self.responder(request, "rh/meu_termo.html", sem_ficha=True)
        situacao = svc.situacao_de(meu)
        termo = None
        if situacao != "assinado":
            try:
                termo = self.termo_para_assinar(meu)
            except ErroDeFormulario as e:
                return self.responder(request, "rh/meu_termo.html", bloqueado=str(e))
        else:
            termo = svc.termo_atual(meu)
        return self.responder(
            request, "rh/meu_termo.html",
            termo=termo, c=meu, situacao=situacao, aviso_modelo=svc.AVISO_DO_MODELO,
            erro=erro, erro_campo=campo, cpf_mascarado=mascarar_cpf(meu.cpf),
            acao=reverse("rh_meu_termo"),
        )

    def post(self, request):
        meu = self.meu(request)
        if meu is None:
            raise Http404()
        ip, _ = ip_da_requisicao(request)
        if svc.tentativas_estouradas(ip):
            return self._falhou(request, "Muitas tentativas seguidas. Espere alguns minutos.", "")
        with transaction.atomic():
            termo = (
                TermoExclusividade.objects.select_for_update().select_related("colaborador")
                .filter(colaborador=meu, versao=svc.VERSAO_DO_TERMO, situacao=TermoExclusividade.Estado.ENVIADO)
                .order_by("-id").first()
            )
            if termo is None:
                if svc.situacao_de(meu) == "assinado":
                    messages.info(request, "Seu termo já está assinado.")
                    return redirect("rh_meu_termo")
                return self._falhou(request, "O termo mudou enquanto você lia. Leia de novo e assine.", "")
            if str(termo.pk) != request.POST.get("termo", ""):
                return self._falhou(request, "O termo mudou enquanto você lia. Leia de novo e assine.", "")
            erro, campo = _assinar(request, termo, TermoExclusividade.Canal.PAINEL)
            if erro:
                transaction.set_rollback(True)
                return self._falhou(request, erro, campo)
        messages.success(request, "Termo assinado. Obrigado! A cópia em PDF está na sua ficha.",
                         extra_tags="titulo:Termo assinado")
        if _quer_json(request):
            return JsonResponse({"ok": True, "destino": reverse("rh_meu_termo")})
        return redirect("rh_meu_termo")

    def _falhou(self, request, erro, campo):
        if _quer_json(request):
            return JsonResponse({"ok": False, "msg": erro, "campo": campo}, status=400)
        return self.get(request, erro=erro, campo=campo)


class TermoColaboradorView(BaseRH):
    """Para a Gestão: a situação do termo de uma pessoa, o QR e o link."""

    aba = "colaboradores"
    funcoes_necessarias = (GESTAO,)

    def get(self, request, pk):
        colaborador = get_object_or_404(Colaborador, pk=pk)
        termo = svc.termo_atual(colaborador)
        return self.responder(
            request, "rh/termo_colaborador.html",
            c=colaborador, termo=termo, situacao=svc.situacao_de(colaborador),
            rotulos=svc.ROTULOS, aviso_modelo=svc.AVISO_DO_MODELO,
            validade_minutos=svc.VALIDADE_DO_LINK // 60,
            assinados=colaborador.termos.filter(situacao=TermoExclusividade.Estado.ASSINADO),
            versao=svc.VERSAO_DO_TERMO,
        )

    def post(self, request, pk):
        colaborador = get_object_or_404(Colaborador, pk=pk)
        acao = request.POST.get("action")
        if acao == "gerar":
            try:
                svc.gerar(colaborador, request.user)
            except ErroDeFormulario as erro:
                messages.error(request, str(erro))
                return redirect("rh_termo", pk=pk)
            messages.success(
                request,
                f"Termo enviado para {colaborador.primeiro_nome} assinar"
                + (" (aparece no painel dele)." if colaborador.usuario_id else ": mostre o QR ou mande o link."),
            )
            return redirect(destino_padrao(request, pk))
        if acao == "link":
            termo = svc.termo_atual(colaborador)
            if termo is None or not termo.aguardando:
                return JsonResponse({"status": "erro", "msg": "Envie o termo para assinatura primeiro."}, status=409)
            token, expira_em = svc.emitir_link(termo)
            link = f"{endereco_do_site_interno(request)}{reverse('rh_termo_publico', args=[token])}"
            mensagem = svc.mensagem_whatsapp(termo, link)
            telefone = "55" + colaborador.telefone if colaborador.telefone else ""
            return JsonResponse({
                "status": "sucesso",
                "link": link,
                "qr": svc.assinatura_base.qr_svg(link),
                "expira_em": expira_em * 1000,
                "agora": int(timezone.now().timestamp() * 1000),
                "validade": svc.VALIDADE_DO_LINK,
                "numero": termo.links_gerados,
                "whatsapp": f"https://wa.me/{telefone}?text={quote(mensagem, safe='')}",
            })
        return JsonResponse({"status": "erro", "msg": "Ação inválida."}, status=400)


def destino_padrao(request, pk):
    from sistema_interno.utils import destino_de_retorno

    return destino_de_retorno(request, request.POST.get("voltar"), reverse("rh_termo", args=[pk]))


def endereco_do_site_interno(request):
    """O link do termo abre no PAINEL (interno.), onde a rota existe."""
    return f"{request.scheme}://{request.get_host()}"


class TermoTodosView(BaseRH):
    funcoes_necessarias = (GESTAO,)
    http_method_names = ["post"]

    def post(self, request):
        total = svc.gerar_para_todos(request.user)
        if total:
            messages.success(request, f"Termo enviado para {total} colaborador{'es' if total != 1 else ''} assinar.")
        else:
            messages.info(request, "Ninguém pendente: todos já têm o termo enviado ou assinado.")
        return redirect(reverse("rh_colaboradores") + "?termo=pendente")


class TermoViaView(BaseRH):
    """O termo em folha A4 (assinado ou não), para ler ou "Salvar em PDF"."""

    def get(self, request, pk):
        termo = TermoExclusividade.objects.select_related("colaborador").filter(pk=pk).first()
        if termo is None or not (acesso.gere(request.user) or acesso.eh_o_proprio(request.user, termo.colaborador)):
            raise Http404()
        return sem_cache(render(request, "rh/folha_termo.html", {
            "termo": termo, "doc": termo.conteudo or {}, "painel": True,
            "assinatura_img": _data_url(termo), "cpf_assinante": termo.assinante_cpf,
            "voltar_url": (
                reverse("rh_termo", args=[termo.colaborador_id]) if acesso.gere(request.user)
                else reverse("rh_meu_termo")
            ),
            "imprimir_ao_abrir": request.GET.get("imprimir") == "1",
        }))


def _data_url(termo):
    import base64

    if not termo.assinatura_png:
        return ""
    return "data:image/png;base64," + base64.b64encode(bytes(termo.assinatura_png)).decode("ascii")


# ======================================================================
# A PÁGINA DO LINK (sem login)
# ======================================================================
STATUS = {"expirado": 410, "substituido": 410, "invalido": 404}
MENSAGENS = {
    "expirado": "O tempo deste link acabou. Peça um novo a quem mostrou o QR.",
    "substituido": "Este link é de uma versão anterior do termo. Peça o link novo.",
    "invalido": "Link inválido.",
}


def _cabecalhos(resposta):
    resposta["Cache-Control"] = "no-store"
    resposta["X-Robots-Tag"] = "noindex, nofollow"
    resposta["Referrer-Policy"] = "no-referrer"
    return resposta


class TermoPublicoView(View):
    http_method_names = ["get", "post"]

    def get(self, request, token):
        leitura = svc.ler_link(token)
        if leitura.situacao == "assinado":
            return _cabecalhos(render(request, "rh/termo_publico.html", {
                "estado": "assinado", "termo": leitura.termo, "doc": leitura.termo.conteudo,
            }))
        if not leitura.valido:
            return _cabecalhos(render(request, "rh/termo_publico.html", {
                "estado": leitura.situacao, "mensagem": MENSAGENS[leitura.situacao],
            }, status=STATUS[leitura.situacao]))
        return _cabecalhos(render(request, "rh/termo_publico.html", self.contexto(leitura, token)))

    @staticmethod
    def contexto(leitura, token, **extra):
        termo = leitura.termo
        return {
            "estado": "assinar", "termo": termo, "doc": termo.conteudo, "token": token,
            "segundos_restantes": leitura.segundos_restantes,
            "validade_minutos": svc.VALIDADE_DO_LINK // 60,
            "cpf_mascarado": mascarar_cpf(termo.colaborador.cpf),
            "aviso_modelo": svc.AVISO_DO_MODELO,
            **extra,
        }

    def post(self, request, token):
        ip, _ = ip_da_requisicao(request)
        if svc.tentativas_estouradas(ip):
            return self._erro(request, "Muitas tentativas seguidas. Espere alguns minutos.", "", 429)
        with transaction.atomic():
            leitura = svc.ler_link(token, bloquear=True)
            if leitura.situacao == "assinado":
                return self._erro(request, "Este termo já foi assinado. Nada foi alterado.", "", 409)
            if not leitura.valido:
                return self._erro(request, MENSAGENS[leitura.situacao] + " Nada foi salvo.", "",
                                  STATUS[leitura.situacao])
            erro, campo = _assinar(request, leitura.termo, TermoExclusividade.Canal.LINK)
            if erro:
                transaction.set_rollback(True)
                if _quer_json(request):
                    return _cabecalhos(JsonResponse({"ok": False, "msg": erro, "campo": campo}, status=400))
                return _cabecalhos(render(
                    request, "rh/termo_publico.html",
                    self.contexto(leitura, token, erro=erro, erro_campo=campo), status=400,
                ))
        destino = reverse("rh_termo_publico", args=[token])
        if _quer_json(request):
            return _cabecalhos(JsonResponse({"ok": True, "destino": destino}))
        return redirect(destino)

    def _erro(self, request, mensagem, campo, status):
        if _quer_json(request):
            return _cabecalhos(JsonResponse({"ok": False, "msg": mensagem, "campo": campo}, status=status))
        return _cabecalhos(render(request, "rh/termo_publico.html", {"estado": "erro", "mensagem": mensagem},
                                  status=status))
