"""Confere, sem adivinhação, se o envio de e-mail está de pé.

    python manage.py testar_email seu-email@exemplo.com

Mostra a configuração que o servidor está usando de verdade (sem expor a
senha), tenta um envio real e diz exatamente o que falhou quando falha --
credencial errada, porta bloqueada ou domínio recusado dão mensagens
diferentes, e é isso que decide onde mexer.
"""

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.core.management.base import BaseCommand, CommandError

from core.email_utils import remetente, responder_para, smtp_configurado


class Command(BaseCommand):
    help = "Envia um e-mail de teste e mostra a configuração SMTP em uso."

    def add_arguments(self, parser):
        parser.add_argument(
            "destino",
            help="Endereço que vai receber o e-mail de teste.",
        )

    def handle(self, *args, **opcoes):
        destino = opcoes["destino"].strip()
        if "@" not in destino:
            raise CommandError(f"'{destino}' não parece um e-mail.")

        senha = getattr(settings, "EMAIL_HOST_PASSWORD", "")
        self.stdout.write(self.style.MIGRATE_HEADING("Configuração atual"))
        for rotulo, valor in (
            ("EMAIL_HOST", settings.EMAIL_HOST),
            ("EMAIL_PORT", settings.EMAIL_PORT),
            ("EMAIL_USE_TLS", settings.EMAIL_USE_TLS),
            ("EMAIL_USE_SSL", settings.EMAIL_USE_SSL),
            ("EMAIL_HOST_USER", settings.EMAIL_HOST_USER or "(vazio)"),
            ("EMAIL_HOST_PASSWORD", "definida" if senha else "(vazia)"),
            ("DEFAULT_FROM_EMAIL", remetente()),
            ("EMAIL_RESPOSTA", responder_para() or "(nenhum)"),
        ):
            self.stdout.write(f"  {rotulo}: {valor}")

        if not smtp_configurado():
            raise CommandError(
                "Faltam EMAIL_HOST_USER e/ou EMAIL_HOST_PASSWORD no "
                "ambiente. Configure e rode de novo."
            )

        mensagem = EmailMultiAlternatives(
            subject="Teste de envio — Lazer & Sport",
            body=(
                "Se você está lendo isto, o envio de e-mail do site está "
                "funcionando.\n\nResponda esta mensagem para conferir "
                "também o endereço de resposta."
            ),
            from_email=remetente(),
            to=[destino],
            reply_to=responder_para(),
            connection=get_connection(fail_silently=False),
        )
        mensagem.attach_alternative(
            "<p>Se você está lendo isto, o envio de e-mail do site está "
            "<strong>funcionando</strong>.</p>",
            "text/html",
        )

        try:
            enviados = mensagem.send(fail_silently=False)
        except Exception as erro:
            raise CommandError(
                f"O servidor SMTP recusou o envio: {type(erro).__name__}: "
                f"{erro}"
            )

        if enviados != 1:
            raise CommandError(
                "O servidor aceitou a conexão mas não confirmou o envio."
            )

        self.stdout.write(
            self.style.SUCCESS(f"E-mail de teste enviado para {destino}.")
        )
