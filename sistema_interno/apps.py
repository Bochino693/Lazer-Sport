from django.apps import AppConfig


class SistemaInternoConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'sistema_interno'

    def ready(self):
        """Liga o sino às gravações deste processo.

        O pulso do sino guarda por poucos segundos o resumo do que existe
        no banco, para dez abas perguntando junto custarem uma consulta e
        não dez. Quem acabou de gravar não pode esperar esses segundos, e
        é isso que estes ouvintes resolvem: gravou neste processo, o
        resumo cai na hora. Ver `pulso.py`.
        """
        from . import pulso, signals_montagem

        pulso.ligar_ouvintes()
        # A lista de montagem acompanha o pedido pago e o orçamento
        # aprovado sozinha (LEIA-ME-V10, seção 112).
        signals_montagem.ligar()

        # Depois de cada `migrate` (o deploy roda um ao subir), a lista se
        # acerta com a regra de agora: a máquina que uma migração tirou da
        # trilha de brinquedão volta à fila das máquinas sem esperar alguém
        # abrir a tela. Banco sem máquinas: uma consulta e acabou.
        from django.db.models.signals import post_migrate

        post_migrate.connect(_acertar_lista_depois_do_migrate, sender=self,
                             dispatch_uid="sistema_interno.montagem.post_migrate")


def _acertar_lista_depois_do_migrate(sender, using="default", **kwargs):
    import logging

    from django.db import DEFAULT_DB_ALIAS, transaction

    if using != DEFAULT_DB_ALIAS:
        return
    try:
        from . import montagem

        with transaction.atomic(using=using):
            montagem.reclassificar()
    except Exception:  # noqa: BLE001 -- o deploy nunca para por causa da lista
        logging.getLogger(__name__).exception("Lista de montagem: reclassificar depois do migrate falhou")
