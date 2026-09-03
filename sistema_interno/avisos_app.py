"""Avisar no celular de quem baixou o aplicativo.

O QUE ISTO RESOLVE. A loja só existia para quem resolvia abrir a loja.
Um brinquedo novo entrava no catálogo e ficava esperando; uma promoção
de fim de semana dependia de a pessoa lembrar do site no sábado. Quem
instalou o aplicativo já disse que quer ouvir a gente -- e não havia por
onde falar.

COMO A MENSAGEM CHEGA. Pelo mesmo caminho que o painel usa para avisar a
equipe: Web Push (`sistema_interno/push.py`), cifrado de ponta a ponta,
entregue pelo serviço do fabricante -- Google no Android, Apple no
iPhone. Não é uma segunda implementação, é a mesma, com outro público.

O QUE ISSO EXIGE DE CADA APARELHO:

  * ANDROID -- basta aceitar o pedido de permissão;
  * IPHONE -- o site precisa estar ADICIONADO À TELA DE INÍCIO. A Apple
    não entrega notificação para página aberta no Safari, e essa é a
    diferença que mais confunde quem testa ("no Android chega e no meu
    não"). Por isso a tela do site pede a instalação antes de oferecer o
    aviso, em vez de mostrar um botão que não faria nada.

DISPARO EM LOTE, SEM SEGURAR A TELA. O envio percorre os aparelhos um a
um, com um limite de tempo por aparelho (ver `push.ESPERA`). Aparelho
que respondeu "não existo mais" é APAGADO na hora: aplicativo
desinstalado é o caso comum, e insistir para sempre num endereço morto é
o que transforma uma lista viva numa lista de fantasmas.
"""

from __future__ import annotations

import logging

from django.utils import timezone

from . import push
from .models import AparelhoDoCliente, AvisoDoAplicativo

log = logging.getLogger(__name__)

#: Teto por disparo. Não é medo de volume -- é que um POST que percorre
#: dez mil aparelhos seguraria o worker por minutos e o gunicorn o
#: derrubaria no meio, deixando metade avisada e ninguém sabendo qual
#: metade. Acima disto, o envio é feito em levas pela mesma tela.
LIMITE_POR_DISPARO = 500


def aparelhos_do_publico(publico):
    """Os aparelhos que este aviso alcança, na ordem de quem chegou antes."""
    consulta = AparelhoDoCliente.objects.all()
    if publico == AvisoDoAplicativo.Publico.ANDROID:
        consulta = consulta.filter(plataforma=AparelhoDoCliente.Plataforma.ANDROID)
    elif publico == AvisoDoAplicativo.Publico.IOS:
        consulta = consulta.filter(plataforma=AparelhoDoCliente.Plataforma.IOS)
    return consulta.order_by("criacao", "id")


def resumo_do_publico():
    """Quantos aparelhos existem, por plataforma -- para a tela mostrar."""
    total = AparelhoDoCliente.objects.count()
    android = AparelhoDoCliente.objects.filter(
        plataforma=AparelhoDoCliente.Plataforma.ANDROID
    ).count()
    ios = AparelhoDoCliente.objects.filter(
        plataforma=AparelhoDoCliente.Plataforma.IOS
    ).count()
    return {
        "total": total,
        "android": android,
        "ios": ios,
        "outros": total - android - ios,
    }


def corpo_do_aviso(aviso, base_do_site=""):
    """O pacote que o celular recebe.

    Os nomes das chaves são os que o service worker do site lê ao
    desenhar a notificação -- ver `core/static/site/ls-app-sw.js`. Mudar
    um aqui sem mudar lá entrega uma notificação em branco.
    """
    destino = (aviso.url or "/").strip()
    if base_do_site and destino.startswith("/"):
        destino = base_do_site.rstrip("/") + destino

    return {
        "titulo": aviso.titulo,
        "mensagem": aviso.mensagem,
        "url": destino,
        "aviso": aviso.pk,
    }


def disparar(aviso, base_do_site="", limite=LIMITE_POR_DISPARO):
    """Entrega o aviso e devolve o que aconteceu.

    Nunca levanta por falha de rede nem de um aparelho: o disparo tem de
    terminar e contar o resultado, e não morrer no meio por causa de um
    telefone desligado.
    """
    if not push.configurado():
        return {
            "enviado": False,
            "motivo": (
                "As notificações não estão ligadas nesta hospedagem: falta "
                "a chave da aplicação (VAPID). Ver docs/APP_PONTOS.md."
            ),
            "entregues": 0,
            "falhas": 0,
            "alcance": 0,
        }

    aparelhos = list(aparelhos_do_publico(aviso.publico)[:limite])
    dados = corpo_do_aviso(aviso, base_do_site)

    entregues = 0
    falhas = 0
    mortos = []

    for aparelho in aparelhos:
        try:
            saiu = push.enviar(
                aparelho.endpoint, aparelho.p256dh, aparelho.auth, dados,
            )
        except push.InscricaoMorta:
            # Aplicativo desinstalado, dados do site limpos, telefone
            # trocado. Some da lista: é o próprio serviço do fabricante
            # dizendo que aquele endereço não existe mais.
            mortos.append(aparelho.pk)
            continue
        except Exception:  # noqa: BLE001 - um aparelho não derruba o lote
            log.exception("Falha inesperada ao avisar aparelho %s", aparelho.pk)
            falhas += 1
            continue

        if saiu:
            entregues += 1
            aparelho.ultimo_aviso = timezone.now()
            aparelho.save(update_fields=["ultimo_aviso", "atualizado"])
        else:
            falhas += 1

    if mortos:
        AparelhoDoCliente.objects.filter(pk__in=mortos).delete()

    aviso.status = AvisoDoAplicativo.Status.ENVIADO
    aviso.enviado_em = timezone.now()
    aviso.aparelhos_no_envio = len(aparelhos)
    aviso.entregues = entregues
    aviso.falhas = falhas
    aviso.save(update_fields=[
        "status", "enviado_em", "aparelhos_no_envio",
        "entregues", "falhas", "atualizado",
    ])

    return {
        "enviado": True,
        "motivo": "",
        "entregues": entregues,
        "falhas": falhas,
        "alcance": len(aparelhos),
        "removidos": len(mortos),
    }
