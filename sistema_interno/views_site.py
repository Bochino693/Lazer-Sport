"""Pontes seguras entre o aplicativo interno e a vitrine pública."""

from django.http import HttpResponseRedirect
from django.views import View

from .views import InternoRequiredMixin


def host_publico(request) -> str:
    host = request.get_host()
    nome, separador, porta = host.partition(":")
    if nome.startswith("interno."):
        nome = nome[len("interno."):]
    return nome + (separador + porta if separador else "")


class LinkSitePublicoView(InternoRequiredMixin, View):
    """Abre uma página pública sem depender do urlconf do subdomínio."""

    def get(self, request, pk=None, tipo="home"):
        caminho = f"/combo/{pk}" if tipo == "combo" and pk else "/"
        esquema = "https" if request.is_secure() else "http"
        return HttpResponseRedirect(f"{esquema}://{host_publico(request)}{caminho}")
