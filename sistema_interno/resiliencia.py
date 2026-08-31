"""Respostas de recuperação do painel sem depender de contexto ou banco."""

from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.template import engines
from django.urls import reverse


def _pede_json(request):
    return (
        request.headers.get("X-Requested-With") in {
            "XMLHttpRequest",
            "LS-Soft-Navigation",
        }
        or "application/json" in request.headers.get("Accept", "")
    )


def resposta_temporaria(request, motivo="temporario"):
    request_id = getattr(request, "ls_request_id", "")
    if _pede_json(request):
        resposta = JsonResponse(
            {
                "status": "retry",
                "msg": (
                    "A conexão oscilou. Nada foi reenviado; tente novamente "
                    "quando a rede estabilizar."
                ),
                "request_id": request_id,
            },
            status=503,
        )
    else:
        # Renderização deliberadamente sem RequestContext: se o banco caiu,
        # context processors não podem provocar uma segunda falha.
        template = engines["django"].get_template("erro_temporario_inner.html")
        html = template.render({"request_id": request_id})
        resposta = HttpResponse(html, status=503, content_type="text/html; charset=utf-8")

    resposta["Retry-After"] = "3"
    resposta["Cache-Control"] = "no-store"
    resposta["X-LS-Retryable"] = "1"
    resposta["X-LS-Recovery"] = motivo
    return resposta


def erro_interno(request):
    return resposta_temporaria(request, motivo="erro-interno")


def pagina_interna_nao_encontrada(request, exception=None):
    """Recupera links antigos sem transformar gravações em falsos sucessos."""
    if _pede_json(request):
        return JsonResponse(
            {
                "status": "stale",
                "msg": "Esta tela ou registro não existe mais. Atualize a listagem.",
                "request_id": getattr(request, "ls_request_id", ""),
            },
            status=409,
        )

    destino = reverse("home_inner", urlconf="sistema_interno.urls")
    return redirect(f"{destino}?recuperado=pagina")
