"""Os avisos que vão para o CLIENTE -- não para a equipe.

POR QUE É UM ARQUIVO SEPARADO. `notificacoes.py` cuida de quem trabalha
aqui dentro: o telefone da equipe toca quando algo precisa ser feito. Este
cuida de quem está do lado de fora, e o objetivo é outro -- não é mandar
executar, é lembrar de decidir.

A diferença aparece no texto, e é por isso que os dois não cabem no mesmo
lugar. O aviso da equipe diz "isto precisa da sua ação"; o do cliente diz
"o seu prazo está acabando, e a decisão é sua". Um lembra de cobrar, o
outro lembra de responder. Um texto só para os dois públicos vira ou uma
cobrança para o cliente ou um recado ameno para a equipe.

A DIFERENÇA DE CANAL TAMBÉM É REAL. A equipe tem o painel instalado e
recebe push no aparelho; o cliente não instala nada e não se inscreve em
nada. O que chega nele é e-mail -- e, quando alguém da equipe manda, a
mensagem de WhatsApp. Por isso aqui não há push: seria escrever para um
canal que não existe.

O BURACO QUE ISTO FECHA. A central de avisos já cobrava a equipe quando
uma proposta estava para vencer. O cliente não recebia nada. Ou seja: o
sistema sabia que a data ia passar, avisava quem não podia decidir, e
ficava calado com quem podia. A proposta expirava, e o motivo mais comum
não era "o cliente não quis" -- era "o cliente esqueceu".
"""

from __future__ import annotations

import logging

from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

from core.email_utils import (
    cnpj_empresa,
    nome_empresa,
    remetente,
    responder_para,
    smtp_configurado,
)

from .models import EnvioOrcamento, Orcamento
from .utils import endereco_do_site

log = logging.getLogger(__name__)

#: A partir de quantos dias restantes o cliente é lembrado. Igual ao que a
#: equipe já usa para cobrar (`avisos.DIAS_PARA_COBRAR`): os dois lados da
#: mesma conversa começam no mesmo dia, e ninguém é pego de surpresa.
DIAS_PARA_LEMBRAR = 3

#: Um lembrete por proposta. Perseguir cliente com e-mail é o caminho
#: mais curto para a caixa de spam -- e para o cliente parar de abrir
#: qualquer coisa que venha da gente.
CANAL_LEMBRETE = EnvioOrcamento.Canal.EMAIL
DETALHE_LEMBRETE = "lembrete-de-validade"


def _prazo_em_palavras(dias):
    if dias <= 0:
        return "hoje"
    if dias == 1:
        return "amanhã"
    return f"em {dias} dias"


def propostas_a_lembrar(hoje=None, dias=DIAS_PARA_LEMBRAR):
    """Enviadas, sem resposta, vencendo, e que ainda não foram lembradas.

    As quatro condições importam. Rascunho não foi para ninguém; proposta
    respondida não precisa de lembrete; a que já venceu perdeu o assunto
    (a automação a expira); e a já lembrada não pode receber de novo --
    perseguir cliente por e-mail é o caminho mais curto para o spam.
    """
    hoje = hoje or timezone.localdate()
    limite = hoje + timezone.timedelta(days=dias)

    return (
        Orcamento.objects
        .filter(
            status=Orcamento.Status.AGUARDANDO_RESPOSTA,
            validade__gte=hoje,
            validade__lte=limite,
        )
        .exclude(
            envios__canal=CANAL_LEMBRETE,
            envios__detalhe=DETALHE_LEMBRETE,
        )
        .select_related("cliente")
        .prefetch_related("itens")
        .order_by("validade", "pk")
    )


def lembrar_validade(orcamento, request=None):
    """Manda ao cliente um lembrete de que a proposta está para vencer.

    Devolve True quando o e-mail saiu. Registra a tentativa em
    `EnvioOrcamento` -- com sucesso ou sem --, que é o mesmo lugar onde o
    comercial já lê o histórico de envio da proposta: quem abrir a tela
    vê que o lembrete saiu, e não pergunta de novo.
    """
    destino = (orcamento.email_destinatario or "").strip()
    if not destino or not smtp_configurado():
        return False

    dias = orcamento.dias_para_vencer
    if dias is None:
        return False

    link = f"{endereco_do_site(request)}{orcamento.caminho_publico}"
    contexto = {
        "orcamento": orcamento,
        "itens": list(orcamento.itens.all()),
        "link": link,
        "total_formatado": f"{orcamento.total:,.2f}".replace(",", "_").replace(".", ",").replace("_", "."),
        "empresa_nome": nome_empresa(),
        "empresa_cnpj": cnpj_empresa(),
        "dias_restantes": dias,
        "prazo_texto": _prazo_em_palavras(dias),
        "validade_texto": (
            orcamento.validade.strftime("%d/%m/%Y") if orcamento.validade else ""
        ),
    }

    assunto = (
        f"Sua proposta nº {orcamento.pk} vence {contexto['prazo_texto']}"
    )
    html = render_to_string("emails/orcamento_lembrete.html", contexto)
    texto = (
        f"Olá, {orcamento.destinatario}.\n\n"
        f"Sua proposta nº {orcamento.pk} vence {contexto['prazo_texto']}.\n"
        f"Abra e responda: {link}\n\n"
        "Precisa de mais prazo ou quer ajustar algo? É só responder este e-mail."
    )

    erro = ""
    try:
        mensagem = EmailMultiAlternatives(
            subject=assunto,
            body=texto,
            from_email=remetente(),
            to=[destino],
            reply_to=responder_para(orcamento.responsavel),
        )
        mensagem.attach_alternative(html, "text/html")
        mensagem.send(fail_silently=False)
        saiu = True
    except Exception as falha:  # noqa: BLE001 - o motivo vai para o histórico
        # Um SMTP fora do ar não pode derrubar o ciclo do observador nem
        # sumir sem explicação: a falha vira registro e aparece na tela.
        log.warning("Lembrete da proposta %s não saiu: %s", orcamento.pk, falha)
        erro = str(falha)[:300]
        saiu = False

    EnvioOrcamento.objects.create(
        orcamento=orcamento,
        canal=CANAL_LEMBRETE,
        destino=destino,
        sucesso=saiu,
        detalhe=DETALHE_LEMBRETE if saiu else f"{DETALHE_LEMBRETE}: {erro}",
        responsavel=orcamento.responsavel,
    )
    return saiu


def lembrar_propostas_a_vencer(hoje=None):
    """Passa uma vez por todas as propostas que merecem lembrete.

    Chamada pelo observador de pendências, junto das outras automações.
    Idempotente: a proposta lembrada sai da consulta no ciclo seguinte.
    """
    enviados = 0
    for orcamento in propostas_a_lembrar(hoje=hoje):
        if lembrar_validade(orcamento):
            enviados += 1
    return enviados
