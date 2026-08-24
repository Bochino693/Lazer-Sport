"""Avisos ao cliente quando o pagamento é aprovado.

O pagamento pode ser confirmado com o cliente longe do site — pelo webhook
do Mercado Pago, no meio da noite. Por isso a confirmação não pode depender
da aba aberta: ela vira estado no `Pedido` e é entregue por dois caminhos
independentes, o e-mail e o aviso na tela quando ele voltar.

O envio roda em uma thread para não segurar o webhook: o SMTP tem timeout de
10 s e o Mercado Pago reenvia a notificação se demorarmos a responder — o
pagamento nunca deve esperar o servidor de e-mail.
"""

import logging
import threading

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import close_old_connections
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.formats import number_format
from django.utils.html import strip_tags

logger = logging.getLogger("pagamentos")


def _email_do_pedido(pedido):
    """E-mail do comprador, com o cadastro do usuário como fonte principal."""
    cliente = getattr(pedido, "cliente", None)
    if not cliente:
        return ""

    usuario = getattr(cliente, "user", None)
    return (getattr(usuario, "email", "") or "").strip()


def _nome_do_pedido(pedido):
    cliente = getattr(pedido, "cliente", None)
    if not cliente:
        return "cliente"

    nome = (getattr(cliente, "nome_completo", "") or "").strip()
    if nome:
        return nome.split()[0]

    usuario = getattr(cliente, "user", None)
    return (
        (getattr(usuario, "first_name", "") or "").strip()
        or (getattr(usuario, "username", "") or "").strip()
        or "cliente"
    )


def _moeda(valor):
    """1234.5 -> "1.234,50".

    O filtro `floatformat` do template devolve "2500,00" — vírgula certa,
    mas sem separador de milhar, e um total de quatro dígitos fica ruim de
    ler num recibo. Formata aqui, uma vez, direto do Decimal.
    """
    if valor is None:
        return "0,00"
    return number_format(valor, decimal_pos=2, force_grouping=True)


def _url_absoluta(caminho):
    base = (getattr(settings, "SITE_URL", "") or "").rstrip("/")
    if not base:
        base = "https://www.lazersport.com.br"
    return f"{base}{caminho}"


def montar_email_confirmacao(pedido):
    """Monta o e-mail sem enviar. Separado para poder testar o conteúdo."""
    destinatario = _email_do_pedido(pedido)
    if not destinatario:
        return None

    itens = list(pedido.itens.all())

    # Os valores chegam ao template já escritos: assim o mesmo número sai
    # idêntico na versão HTML e na de texto puro.
    linhas = [
        {
            "nome": item.nome_item,
            "quantidade": item.quantidade,
            "subtotal": _moeda(item.subtotal),
        }
        for item in itens
    ]

    contexto = {
        "pedido": pedido,
        "itens": linhas,
        "total_liquido": _moeda(pedido.total_liquido),
        "total_final": _moeda(pedido.total_final),
        "valor_frete": _moeda(pedido.valor_frete),
        "valor_desconto": _moeda(pedido.valor_desconto),
        "primeiro_nome": _nome_do_pedido(pedido),
        "url_pedidos": _url_absoluta(reverse("meus_pedidos") + "#pedidos"),
        "url_site": _url_absoluta("/"),
        "whatsapp": "https://wa.me/5511960563135",
    }

    corpo_html = render_to_string("emails/pedido_confirmado.html", contexto)
    corpo_texto = render_to_string("emails/pedido_confirmado.txt", contexto)

    mensagem = EmailMultiAlternatives(
        subject=f"Pedido #{pedido.id} confirmado — Lazer & Sport",
        body=corpo_texto or strip_tags(corpo_html),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[destinatario],
    )
    mensagem.attach_alternative(corpo_html, "text/html")
    return mensagem


def _marcar_enviado(pedido_id):
    """Grava a marca só depois do envio dar certo.

    Import local: este módulo é importado por core.views, que por sua vez é
    importado durante o carregamento dos models — importar Pedido no topo
    fecharia o ciclo.
    """
    from .models import Pedido

    Pedido.objects.filter(pk=pedido_id).update(
        email_confirmacao_enviado=True,
    )


def _enviar_agora(pedido_id):
    from .models import Pedido

    try:
        pedido = (
            Pedido.objects
            .select_related("cliente__user")
            .prefetch_related("itens")
            .filter(pk=pedido_id)
            .first()
        )
        if not pedido:
            return False

        # Reentrada: duas confirmações do mesmo pagamento (webhook + polling)
        # não podem virar dois e-mails.
        if pedido.email_confirmacao_enviado:
            return False

        mensagem = montar_email_confirmacao(pedido)
        if mensagem is None:
            logger.warning(
                "Pedido %s sem e-mail cadastrado: confirmação não enviada.",
                pedido_id,
            )
            return False

        if not settings.EMAIL_HOST_USER:
            logger.warning(
                "SMTP sem credencial: e-mail do pedido %s não enviado.",
                pedido_id,
            )
            return False

        mensagem.send(fail_silently=False)
        _marcar_enviado(pedido_id)
        logger.info("E-mail de confirmação do pedido %s enviado.", pedido_id)
        return True

    except Exception:
        # O pedido está pago e criado. Um SMTP fora do ar não pode virar erro
        # de pagamento — o campo continua False e uma próxima confirmação
        # (ou um reenvio manual) tenta de novo.
        logger.exception(
            "Falha ao enviar o e-mail de confirmação do pedido %s.",
            pedido_id,
        )
        return False
    finally:
        # A thread abre sua própria conexão com o banco; sem isso ela ficaria
        # ociosa no pool depois que a thread morre.
        close_old_connections()


def enviar_confirmacao_de_compra(pedido, bloqueante=False):
    """Dispara o e-mail de confirmação do pedido.

    Por padrão vai para uma thread: quem chama é o webhook ou o polling do
    checkout, e nenhum dos dois pode ficar esperando o SMTP responder.
    `bloqueante=True` existe para os testes e para o reenvio manual.
    """
    if pedido is None or pedido.email_confirmacao_enviado:
        return False

    if bloqueante:
        return _enviar_agora(pedido.pk)

    thread = threading.Thread(
        target=_enviar_agora,
        args=(pedido.pk,),
        name=f"email-pedido-{pedido.pk}",
        daemon=True,
    )
    thread.start()
    return True
