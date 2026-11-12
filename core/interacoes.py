"""Visitas e idas ao carrinho, hora a hora: o "quando" dos gráficos do painel.

O QUE JÁ EXISTIA. `BrinquedoClick` e os irmãos guardam um número por
produto, somado desde sempre (core/cliques.py). Servem à vitrine e ao
ranking, mas não contam história: não dá para saber se as 300 visitas do
Air Game foram ontem ou no ano passado.

O QUE ISTO ACRESCENTA. A mesma visita, agora também numa linha da HORA em
que aconteceu (`InteracaoPorHora`). É gravada no mesmo lugar e no mesmo
ritmo do contador antigo -- na linha de fundo em produção, na hora no
computador e nos testes --, então a página continua saindo do cache sem
esperar o banco.

NUNCA DERRUBA A PÁGINA. Se a tabela ainda não existir (o código chegou
antes da migração) ou o banco recusar, a visita deixa de ir para o gráfico
e o resto segue: o contador antigo já foi gravado antes, e a página do
cliente não tem nada a ver com isso.
"""

from __future__ import annotations

import logging

from django.db import DatabaseError, IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

log = logging.getLogger("core.interacoes")

VISITA = "visita"
CARRINHO = "carrinho"

#: O contador antigo de cada página -> (alvo daqui, campo que diz qual é o produto).
CONTADORES = {
    "BrinquedoClick": ("brinquedo", "brinquedo_clicado_id"),
    "ComboClick": ("combo", "combo_clicado_id"),
    "PromocaoClick": ("promocao", "promocao_id"),
    "CategoriaClick": ("categoria", "categoria_id"),
}

#: O `tipo` que o carrinho do site e o do aplicativo recebem -> alvo daqui.
ALVO_DO_CARRINHO = {
    "brinquedo": "brinquedo",
    "combo": "combo",
    "promocao": "promocao",
    "peca": "peca",
    "pecas": "peca",
}


def inicio_da_hora(quando=None):
    """O começo da hora, no fuso do site (é a chave da linha)."""
    quando = timezone.localtime(quando or timezone.now())
    return quando.replace(minute=0, second=0, microsecond=0)


def somar(evento, alvo, objeto_id, quantidade=1, hora=None, origem="site"):
    """Soma `quantidade` na linha da hora; a linha nasce na primeira vez. Nunca levanta."""
    try:
        objeto_id = int(objeto_id or 0)
        quantidade = int(quantidade or 0)
    except (TypeError, ValueError):
        return
    if objeto_id <= 0 or quantidade <= 0:
        return

    from .models import InteracaoPorHora

    filtro = {
        "evento": evento,
        "alvo": alvo,
        "objeto_id": objeto_id,
        "hora": hora or inicio_da_hora(),
        "origem": origem,
    }
    try:
        # O savepoint isola a falha: dentro de uma transação (o teste, uma
        # view atômica), uma consulta recusada não pode envenenar o resto.
        with transaction.atomic():
            atualizadas = InteracaoPorHora.objects.filter(**filtro).update(
                quantidade=F("quantidade") + quantidade,
            )
            if not atualizadas:
                InteracaoPorHora.objects.create(quantidade=quantidade, **filtro)
    except IntegrityError:
        # Duas gravações criaram a mesma hora ao mesmo tempo: a outra venceu.
        try:
            with transaction.atomic():
                InteracaoPorHora.objects.filter(**filtro).update(
                    quantidade=F("quantidade") + quantidade,
                )
        except DatabaseError:
            log.warning("interacoes: %s de %s %s não entrou no gráfico", evento, alvo, objeto_id, exc_info=True)
    except DatabaseError:
        log.warning("interacoes: %s de %s %s não entrou no gráfico", evento, alvo, objeto_id, exc_info=True)


def visita_do_contador(modelo, filtro, quantidade, hora=None):
    """Chamado por core/cliques.py logo depois de somar o contador antigo."""
    mapa = CONTADORES.get(getattr(modelo, "__name__", ""))
    if not mapa:
        return
    alvo, campo = mapa
    somar(VISITA, alvo, filtro.get(campo), quantidade, hora=hora)


def ida_ao_carrinho(tipo, objeto_id, quantidade=1, origem="site"):
    """Alguém pôs o produto no carrinho (site ou aplicativo).

    Vai pela mesma linha de fundo dos cliques: o carrinho responde sem
    esperar esta gravação.
    """
    alvo = ALVO_DO_CARRINHO.get((tipo or "").strip().lower())
    if not alvo:
        return
    from . import cliques

    cliques.depois(somar, CARRINHO, alvo, objeto_id, quantidade, inicio_da_hora(), origem)
