"""Respostas de recuperação do painel sem depender de contexto ou banco."""

from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.template import engines
from django.urls import Resolver404, resolve, reverse
from django.conf import settings


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
    # Erro de aplicação não é conexão oscilando: não sinalizar retry.
    return erro_de_pagina(request, 500, "Não foi possível concluir a operação", "O servidor encontrou um erro. Nenhum formulário será reenviado automaticamente. Informe a referência ao suporte.")


def erro_de_pagina(request, status, titulo, mensagem):
    referencia = getattr(request, "ls_request_id", "")
    if _pede_json(request):
        resposta = JsonResponse({"status": "erro", "msg": mensagem, "request_id": referencia}, status=status)
    else:
        template = engines["django"].get_template("erro_navegacao_inner.html")
        resposta = HttpResponse(template.render({
            "titulo": titulo, "mensagem": mensagem, "request_id": referencia,
            "inicio": reverse("home_inner", urlconf="sistema_interno.urls"),
        }), status=status)
    resposta["Cache-Control"] = "no-store"
    resposta["X-LS-Retryable"] = "0"
    return resposta


def pagina_interna_nao_encontrada(request, exception=None):
    """Recupera links antigos sem transformar gravações em falsos sucessos."""
    # Link público aberto no host interno: preservar a página e seus filtros,
    # em vez de encaminhar tudo para a home. Nunca transportar um POST.
    if request.method in ("GET", "HEAD") and not request.path.startswith("/api/"):
        try:
            destino_publico = resolve(request.path, urlconf=settings.ROOT_URLCONF)
        except Resolver404:
            destino_publico = None
        # O catch-all legado da loja não é uma rota pública identificada.
        if destino_publico and destino_publico.url_name:
            from .utils import endereco_do_site
            resposta = redirect(endereco_do_site(request).rstrip("/") + request.get_full_path())
            resposta["Cache-Control"] = "no-store"
            return resposta
    if _pede_json(request):
        return JsonResponse(
            {
                "status": "stale",
                "msg": "Esta tela ou registro não existe mais. Atualize a listagem.",
                "request_id": getattr(request, "ls_request_id", ""),
            },
            status=409,
        )

    return erro_de_pagina(request, 404, "Página não encontrada", "Este endereço não existe ou foi alterado. Use o menu do painel para abrir a tela desejada.")
