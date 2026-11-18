"""Meus pedidos: o código do orçamento e as ações que o cliente faz sozinho.

O PEDIDO, nas palavras do dono: "quando tiver em meus pedidos, vai ter
código do pedido, para o caso do seguinte: o cliente fez o orçamento
conosco pelo telefone, aí faz o cadastro, mas como saber que aquele
orçamento vai virar um pedido do site? através do código, fazendo assim o
acompanhamento e mudança de fases pela internet sem necessidade de
contato." (LEIA-ME-V10, seção 104.)

DUAS PORTAS, AS DUAS POR POST E SÓ PARA QUEM ESTÁ LOGADO:

  * vincular (`VincularOrcamentoView`): o código digitado no quadro "Tem
    um código de orçamento?". A regra mora em
    `sistema_interno.codigo_orcamento.vincular`; aqui ficam o freio de
    tentativas e as mensagens (o sistema de avisos do site: toasts).
  * assinar o termo (`AssinarTermoView`): o link de 5 minutos da
    assinatura, gerado NA HORA pela mesma função do painel
    (`documento_assinatura.emitir_link`), e só para a conta a que o
    orçamento está vinculado. Por POST porque cada link gerado conta no
    documento -- o mesmo motivo do painel.

NADA DE ID NA URL. As duas rotas não têm parâmetro: o código vai no corpo
do formulário, e a conta é a da sessão. Quem não é dono recebe a mesma
resposta de quem digitou um código que não existe.
"""

from __future__ import annotations

import logging
from urllib.parse import quote

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic import View

from core.ls_aviso import avisar
from core.registro_cadastro import ip_da_requisicao
from sistema_interno import codigo_orcamento as svc
from sistema_interno import documento_assinatura as svc_doc

log = logging.getLogger(__name__)

#: O ícone de cada fase do cartão (`codigo_orcamento.Fase.chave`). Mora no
#: `core` porque é desenho do site: o recorte do Font Awesome do site
#: (vendor/fontawesome-site/gerar.py) procura os nomes aqui.
ICONES_DAS_FASES = {
    "proposta": "fa-paper-plane",
    "aprovacao": "fa-handshake-angle",
    "termo": "fa-signature",
    "pagamento": "fa-coins",
    "producao": "fa-industry",
    "entrega": "fa-flag-checkered",
}

#: Onde o código tentado espera a volta para a tela (o campo vem
#: preenchido depois de um erro, para a pessoa só corrigir a letra).
CHAVE_DO_DIGITADO = "codigo_orcamento_digitado"


def _de_volta(ancora="codigo-orcamento"):
    return redirect(f"{reverse('meus_pedidos')}#{ancora}")


def conversa_com_a_equipe(texto):
    """O WhatsApp da empresa, com a mensagem já escrita (ou "" sem número)."""
    numero = "".join(c for c in str(getattr(settings, "ORCAMENTO_WHATSAPP", "") or "") if c.isdigit())
    if not numero:
        return ""
    return f"https://wa.me/{numero}?text={quote(texto, safe='')}"


class VincularOrcamentoView(LoginRequiredMixin, View):
    """O quadro "Tem um código de orçamento?" de Meus pedidos."""

    login_url = "login"
    http_method_names = ["post"]

    def post(self, request):
        texto = (request.POST.get("codigo") or "").strip()[:40]
        ip, _ = ip_da_requisicao(request)

        # O FREIO VEM ANTES DO BANCO: estourado, o código nem é procurado.
        volta = svc.freio_esgotado(request.user, ip)
        if volta is not None:
            request.session[CHAVE_DO_DIGITADO] = texto[:20]
            avisar(
                request,
                "Foram muitos códigos que não serviram seguidos. Por segurança, "
                f"tente de novo a partir das {timezone.localtime(volta):%H:%M}. "
                "Se o código da sua proposta não entra, a equipe resolve pelo WhatsApp.",
                nivel=messages.ERROR,
                titulo="Espere um pouco",
                icone="alerta",
                acao=self._acao_whatsapp(
                    f"Olá! Não consegui vincular o orçamento {texto} em Meus pedidos."
                    if texto else "Olá! Não consegui vincular meu orçamento em Meus pedidos."
                ),
            )
            return _de_volta()

        if not texto:
            avisar(
                request,
                "Digite o código que está na sua proposta, no formato LS-7K3QX9.",
                nivel=messages.WARNING,
                titulo="Falta o código",
            )
            return _de_volta()

        resultado = svc.vincular(texto, request.user)
        if resultado.conta_como_erro:
            svc.contar_erro(request.user, ip)

        if resultado.situacao == "formato":
            request.session[CHAVE_DO_DIGITADO] = texto[:20]
            avisar(
                request,
                f"“{texto[:20]}” não é um código de orçamento. Ele tem o formato "
                "LS-7K3QX9: LS e seis letras e números, sem 0, O, 1, I nem L.",
                nivel=messages.WARNING,
                titulo="Confira o código",
            )
            return _de_volta()

        if resultado.situacao == "inexistente":
            request.session[CHAVE_DO_DIGITADO] = resultado.digitado
            restantes = svc.tentativas_restantes(request.user, ip)
            avisar(
                request,
                f"Nenhum orçamento tem o código {resultado.digitado}. Confira as letras "
                "na proposta (no e-mail, no WhatsApp ou no PDF)."
                + (
                    f" Restam {restantes} tentativa{'s' if restantes != 1 else ''} nesta hora."
                    if restantes <= 3 else ""
                ),
                nivel=messages.ERROR,
                titulo="Código não encontrado",
            )
            return _de_volta()

        if resultado.situacao == "outra_conta":
            avisar(
                request,
                f"O orçamento {resultado.digitado} já está ligado a outra conta do site, "
                "e por isso não foi vinculado à sua. Se ele é seu, fale com a equipe: "
                "ela confere e resolve.",
                nivel=messages.ERROR,
                titulo="Ligado a outra conta",
                acao=self._acao_whatsapp(
                    f"Olá! O orçamento {resultado.digitado} aparece ligado a outra conta "
                    "do site e ele é meu. Podem conferir?"
                ),
            )
            return _de_volta()

        orcamento = resultado.orcamento
        ancora = f"orc-{orcamento.codigo}"
        if resultado.situacao == "ja_era_seu":
            avisar(
                request,
                f"O orçamento {orcamento.codigo} já está na sua conta. "
                "As fases dele estão aqui embaixo.",
                nivel=messages.INFO,
                titulo="Já está com você",
            )
            return _de_volta(ancora)

        texto_ok = f"O orçamento {orcamento.codigo} agora está na sua conta. "
        if resultado.digitado != orcamento.codigo:
            texto_ok = (
                f"O código {resultado.digitado} é de uma versão anterior: vinculamos "
                f"a versão {orcamento.versao}, a que vale agora (código {orcamento.codigo}). "
            )
        acompanhamento = svc.acompanhamento(orcamento)
        if acompanhamento.situacao in ("recusado", "expirado", "substituido"):
            texto_ok += f"Situação: {acompanhamento.situacao_texto.lower()}."
        else:
            texto_ok += "Acompanhe cada fase por aqui, sem precisar ligar."
        avisar(
            request,
            texto_ok,
            nivel=messages.SUCCESS,
            titulo="Orçamento vinculado",
        )
        request.session.pop(CHAVE_DO_DIGITADO, None)
        return _de_volta(ancora)

    @staticmethod
    def _acao_whatsapp(texto):
        url = conversa_com_a_equipe(texto)
        return (url, "Falar com a equipe") if url else None


class AssinarTermoView(LoginRequiredMixin, View):
    """"Assinar o termo": um link novo de 5 minutos, e direto para a assinatura.

    O MESMO LINK DO PAINEL. A equipe manda o QR ou o WhatsApp; aqui o
    próprio cliente pede o dele, pela mesma `emitir_link` -- que conta no
    documento quantos links saíram. As mesmas recusas do painel: sem
    termo gerado, já assinado, ou suspenso (o orçamento deixou de estar
    aprovado). Na página de assinatura valem todas as conferências de
    sempre (o relógio de 5 minutos, o CPF do cadastro, "Li e concordo").
    """

    login_url = "login"
    http_method_names = ["post"]

    def post(self, request):
        orcamento = svc.orcamento_da_conta(request.POST.get("codigo"), request.user)
        if orcamento is None:
            avisar(
                request,
                "Este orçamento não está na sua conta. Vincule o código dele primeiro.",
                nivel=messages.ERROR,
                titulo="Orçamento não encontrado",
            )
            return _de_volta()

        ancora = f"orc-{orcamento.codigo}"
        cartao = svc.acompanhamento(orcamento)
        documento = cartao.documento
        if not cartao.pode_assinar:
            if cartao.termo_assinado is not None:
                texto = "O termo deste orçamento já está assinado. Você pode abrir a cópia no cartão."
            elif documento is None or orcamento.status != orcamento.Status.APROVADO:
                texto = "O termo de compra ainda não está pronto para assinar. Ele aparece aqui assim que a equipe o liberar."
            else:
                texto = "O termo deste orçamento está suspenso. Fale com a equipe para liberar de novo."
            avisar(request, texto, nivel=messages.WARNING, titulo="Assinatura indisponível")
            return _de_volta(ancora)

        token, _expira = svc_doc.emitir_link(documento)
        log.info(
            "Orçamento %s: link de assinatura pedido pelo cliente em Meus pedidos (link %s)",
            orcamento.pk, documento.links_gerados,
        )
        return redirect("documento_assinatura_publico", token=token)
