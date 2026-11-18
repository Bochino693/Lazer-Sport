"""A lista de montagem acompanha a situação do pedido e do orçamento sozinha (seção 108).

"Automatizando o máximo": o pedido do site pago e o orçamento aprovado
entram na lista sem ninguém digitar nada; cancelado, recusado ou
substituído, saem (a vaga libera); o pedido que sai para entrega ou é
finalizado pelo painel de Pedidos leva as máquinas junto.

Como o sinal da venda (core/signals.py): só quando a SITUAÇÃO muda,
depois do commit e "robust" -- o pagamento e o painel nunca falham por
causa da lista, e a lista se acerta de novo ao abrir
(`montagem.sincronizar_tudo`).
"""

import logging

from django.db import transaction
from django.db.models.signals import post_save

logger = logging.getLogger(__name__)


def _situacao_mudou(update_fields):
    return update_fields is None or "status" in update_fields


def pedido_mudou(sender, instance, created, raw=False, update_fields=None, **kwargs):
    if raw or not _situacao_mudou(update_fields):
        return
    if created and instance.status not in ("pago", "em_preparacao"):
        return
    pedido_id = instance.pk

    def acertar():
        from . import montagem

        montagem.sincronizar_pedido(pedido_id)

    transaction.on_commit(acertar, robust=True)


def orcamento_mudou(sender, instance, created, raw=False, update_fields=None, **kwargs):
    if raw or not _situacao_mudou(update_fields):
        return
    if created and instance.status != "aprovado":
        return
    orcamento_id = instance.pk

    def acertar():
        from . import montagem

        montagem.sincronizar_orcamento(orcamento_id)

    transaction.on_commit(acertar, robust=True)


def ligar():
    from core.models import Pedido

    from .models import Orcamento

    post_save.connect(pedido_mudou, sender=Pedido, dispatch_uid="sistema_interno.montagem.pedido")
    post_save.connect(orcamento_mudou, sender=Orcamento, dispatch_uid="sistema_interno.montagem.orcamento")
