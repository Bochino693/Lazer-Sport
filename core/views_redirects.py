"""Redirecionamentos do painel antigo para o aplicativo interno único."""

from django.conf import settings
from django.http import HttpResponseRedirect
from django.urls import reverse


def _origem_interna(request) -> str:
    configurada = getattr(settings, "INTERNO_BASE_URL", "").strip().rstrip("/")
    host = request.get_host()
    nome, separador, porta = host.partition(":")

    if nome in {"localhost", "127.0.0.1"} or nome.endswith(".localhost"):
        return f"http://interno.localhost{separador + porta if separador else ''}"

    if nome.startswith("www."):
        nome = nome[4:]
    if nome in {"lazersport.com.br", "lazersport.com"}:
        return f"https://interno.{nome}"

    return configurada or "https://interno.lazersport.com.br"


def redirecionar_interno(nome_rota):
    """Cria uma view 302; não cacheia o destino durante a transição."""
    def view(request, *args, **kwargs):
        caminho = reverse(
            nome_rota,
            args=args or None,
            kwargs=kwargs or None,
            urlconf="sistema_interno.urls",
        )
        return HttpResponseRedirect(_origem_interna(request) + caminho)

    return view
