from django.apps import AppConfig


class ContasConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "contas"
    verbose_name = "Contas e segurança"

    def ready(self):
        # A guarda do e-mail (pre_save do User e do endereço do allauth) e a
        # contagem das senhas erradas que chegam por fora das telas da casa
        # (o /accounts/login/ do allauth, por exemplo).
        from . import freio, guarda

        guarda.ligar()
        freio.ligar_sinais()
