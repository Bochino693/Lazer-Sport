from django.apps import AppConfig


class RhConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "rh"
    verbose_name = "Recursos humanos"

    def ready(self):
        # Apagar um documento do banco apaga o arquivo do armazenamento
        # privado (e nunca o contrário). Ver `sinais.py`.
        from . import sinais  # noqa: F401
