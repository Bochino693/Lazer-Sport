"""A lista de montagem acompanha a situação do pedido e do orçamento sozinha (seção 112).

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


def tarefa_do_rh_mudou(sender, tarefa=None, situacao=None, por=None, **kwargs):
    """A pessoa concluiu a etapa pelo RH (o celular dela): a máquina anda junto.

    Só para a frente: a etapa já feita, a máquina fora de produção ou a
    tarefa de outra coisa não mudam nada. A lista também cria a tarefa da
    etapa seguinte (montagem.sincronizar_tarefas). Erro aqui nunca derruba
    a tela do RH.
    """
    try:
        from rh.models import Tarefa
    except Exception:  # noqa: BLE001
        return
    if tarefa is None or situacao != Tarefa.Estado.FEITA or not tarefa.etapa:
        return
    try:
        from django.contrib.contenttypes.models import ContentType

        from . import montagem
        from .models import UnidadeMontagem

        if tarefa.content_type_id != ContentType.objects.get_for_model(UnidadeMontagem).pk:
            return
        unidade = UnidadeMontagem.objects.select_related("producao").filter(pk=tarefa.object_id).first()
        if unidade is None or unidade.situacao != UnidadeMontagem.Situacao.PRODUCAO:
            return
        chave = next((c for c, rotulo, _ in montagem.etapas_da(unidade.trilha) if rotulo == tarefa.etapa), None)
        if chave is None or chave in (unidade.etapas_em or {}):
            return
        usuario = por if getattr(por, "is_authenticated", False) else None
        with transaction.atomic():
            montagem.concluir_ate(unidade, chave, usuario=usuario)
    except ValueError:
        return
    except Exception:  # noqa: BLE001
        logger.exception("Tarefa %s do RH -> lista de montagem", getattr(tarefa, "pk", None))


def ligar():
    from core.models import Pedido

    from .models import Orcamento

    post_save.connect(pedido_mudou, sender=Pedido, dispatch_uid="sistema_interno.montagem.pedido")
    post_save.connect(orcamento_mudou, sender=Orcamento, dispatch_uid="sistema_interno.montagem.orcamento")
    try:
        from rh.tarefas import tarefa_mudou
    except Exception:  # noqa: BLE001 -- sem o app do RH, a lista anda só pelo painel
        return
    tarefa_mudou.connect(tarefa_do_rh_mudou, dispatch_uid="sistema_interno.montagem.tarefa_do_rh")
