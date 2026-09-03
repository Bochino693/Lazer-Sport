"""Aplica a identidade visual a todo envio Django antes do transporte SMTP."""
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import get_connection
from django.core.mail.backends.base import BaseEmailBackend
from .email_branding import aplicar_logo


class EmailBackend(BaseEmailBackend):
    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently)
        transporte = getattr(settings, "EMAIL_TRANSPORT_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
        if transporte == "core.email_backend.EmailBackend":
            raise ImproperlyConfigured("EMAIL_TRANSPORT_BACKEND não pode apontar para o próprio decorador.")
        self.transporte = get_connection(transporte, fail_silently=fail_silently, **kwargs)

    def open(self):
        return self.transporte.open()

    def close(self):
        return self.transporte.close()

    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        return self.transporte.send_messages([aplicar_logo(mensagem) for mensagem in email_messages])
