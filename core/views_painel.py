"""O endereço que o quadro inicial da home consulta para ficar ao vivo."""

from django.http import JsonResponse
from django.views.decorators.http import require_GET

from . import painel_publico


@require_GET
def painel_ao_vivo(request):
    resposta = JsonResponse(painel_publico.numeros())
    # O painel já guarda os números por um minuto no servidor; o navegador
    # e o proxy podem segurar meio minuto sem que ninguém perceba.
    resposta["Cache-Control"] = "public, max-age=30"
    return resposta
