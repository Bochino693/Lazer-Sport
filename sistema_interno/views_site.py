"""Pontes seguras entre o aplicativo interno e a vitrine pública."""

from django.http import HttpResponseRedirect
from django.views import View

from .views import InternoRequiredMixin
from .utils import endereco_do_site


def host_publico(request) -> str:
    host = request.get_host()
    nome, separador, porta = host.partition(":")
    if nome.startswith("interno."):
        nome = nome[len("interno."):]
    return nome + (separador + porta if separador else "")


class LinkSitePublicoView(InternoRequiredMixin, View):
    """Abre uma página pública sem depender do urlconf do subdomínio."""

    def get(self, request, pk=None, tipo="home"):
        caminho = f"/combo/{pk}" if tipo == "combo" and pk else "/loja/" if tipo == "loja" else "/"
        resposta = HttpResponseRedirect(endereco_do_site(request).rstrip("/") + caminho)
        resposta["Cache-Control"] = "no-store"
        return resposta
