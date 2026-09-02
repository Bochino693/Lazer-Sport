from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self):
        import core.signals  # noqa: F401

        # A instância não pode dormir: voltar do sono custa de vinte a
        # sessenta segundos, e é isso que a fábrica sente como "o sistema
        # está travado". Ver `core/sempre_pronto.py`.
        from core import sempre_pronto

        sempre_pronto.ligar()
