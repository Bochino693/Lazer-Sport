"""GET /avisos/resolver/<chave>/ -- o que a folha do aviso mostra (seção 116).

Só leitura: a folha grava pelos endereços que as telas já usam, cada um
com a conferência de permissão dele (ver `resolver_avisos.py`). Aqui se
confere quem abre a folha -- a mesma capacidade que dá o aviso.
"""

from django.core.exceptions import PermissionDenied
from django.http import Http404, JsonResponse
from django.views.generic import View

from .resolver_avisos import montar
from .views import InternoRequiredMixin


class ResolverAvisoView(InternoRequiredMixin, View):
    """A lista do que falta e as ações que cabem à função de quem abriu."""

    def get(self, request, chave):
        try:
            corpo = montar(request.user, chave, request)
        except PermissionDenied:
            return JsonResponse({
                "status": "erro",
                "msg": "Este aviso não é da sua função: ele não aparece no seu sino.",
            }, status=403)
        except Http404:
            # 404 escrito aqui, e não levantado: o tratador do painel
            # transforma o 404 de um pedido JSON em "atualize a lista"
            # (409), e aqui o certo é "este aviso abre a tela".
            return JsonResponse({
                "status": "erro",
                "msg": "Este aviso não tem conserto pelo sino. Abra a tela dele.",
            }, status=404)
        resposta = JsonResponse(corpo)
        # Lista de clientes e propostas de uma pessoa: nada guarda isto.
        resposta["Cache-Control"] = "no-store, private"
        resposta["X-LS-No-Store"] = "1"
        return resposta
