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
        # aprovado sozinha (LEIA-ME-V10, seção 108).
        signals_montagem.ligar()
