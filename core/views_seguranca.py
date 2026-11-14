"""O token de segurança (CSRF) que o JS do site usa nos pedidos.

O QUE ACONTECIA (Black Friday de 2026). Com a conta logada, nenhum item
entrava no carrinho: "Não foi possível adicionar este item". O servidor
recusava o pedido por CSRF e respondia com a página 403 do Django, em
HTML -- e a folha do carrinho, que espera JSON, só sabia dizer o texto
genérico. Sem login funcionava; a tela do carrinho (que usa o token
impresso na página) também.

A causa: o navegador guardava DOIS cookies `csrftoken` -- um antigo, do
tempo em que o cookie era só de www.lazersport.com.br, e o atual, de
.lazersport.com.br (COOKIE_DOMAIN). O JS lia o primeiro (o velho) e o
Django lê o último (o atual): o token nunca batia.

O conserto tem três partes:
  * o <head> do site (base.html) apaga o cookie velho e entrega o token
    impresso na página (window.LSCsrf), que é sempre o que o Django lê;
  * `token_csrf` devolve um token novo em JSON: o JS, quando o servidor
    recusa o token, pega este e tenta de novo uma vez, sem o cliente ver;
  * `falha_csrf` responde a recusa em JSON para quem pediu por fetch, com
    um recado que diz o que fazer, e registra o motivo no log.
"""

import logging

from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.csrf import csrf_failure as _falha_padrao
from django.views.decorators.cache import never_cache

logger = logging.getLogger("core.seguranca")

RECADO_CSRF = (
    "Esta página ficou desatualizada. Atualize a página e tente de novo "
    "-- se continuar, fale com a gente no WhatsApp (11) 96056-3135."
)


@never_cache
def token_csrf(request):
    """Um token válido para esta sessão (e o cookie, se faltar)."""
    return JsonResponse({"token": get_token(request)})


def _pediu_json(request):
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return True
    if "application/json" in (request.headers.get("Accept") or ""):
        return True
    return "application/json" in (request.content_type or "")


def falha_csrf(request, reason=""):
    """CSRF_FAILURE_VIEW: JSON para o fetch, a página padrão para o resto."""
    cookie = request.META.get("HTTP_COOKIE", "")
    logger.warning(
        "CSRF recusado: %s %s motivo=%s cookies_csrf=%s logado=%s",
        request.method,
        request.path,
        reason,
        cookie.count("csrftoken="),
        bool(getattr(getattr(request, "user", None), "is_authenticated", False)),
    )
    if _pediu_json(request):
        return JsonResponse(
            {"sucesso": False, "ok": False, "codigo": "csrf", "erro": RECADO_CSRF},
            status=403,
        )
    return _falha_padrao(request, reason=reason)
