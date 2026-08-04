# core/api/auth_app_views.py
#
# LOGIN SOCIAL PARA O APP.
#
# O problema do jeito antigo: o app abria a URL do allauth no navegador
# e acabava ali. O cliente logava no SITE e voltava pro app ainda
# deslogado -- o token nunca atravessava.
#
# Fluxo novo (funciona com o Google e o Apple que o site já tem):
#
#   1. app abre  /api/v1/auth/app/entrar/?provedor=google
#   2. Django manda pro allauth do provedor
#   3. allauth loga e volta pra /api/v1/auth/app/token/
#   4. essa view cria o Token e redireciona pra
#        lazersport://auth?token=...&nome=...&email=...
#   5. o Android intercepta esse esquema e salva o token
#
# Nada de SDK do Google no APK, nada de chave nova: reaproveita a
# configuração social que já está no ar.

from urllib.parse import urlencode

from django.conf import settings
from django.shortcuts import redirect
from django.views import View
from rest_framework.authtoken.models import Token

PROVEDORES = {
    "google": "/accounts/google/login/",
    "apple": "/accounts/apple/login/",
}


def _deep_link(**parametros):
    base = getattr(settings, "APP_DEEP_LINK", "lazersport://auth")
    limpos = {k: v for k, v in parametros.items() if v not in (None, "")}
    return f"{base}?{urlencode(limpos)}"


class AppEntrarSocial(View):
    """GET /api/v1/auth/app/entrar/?provedor=google"""

    def get(self, request):
        provedor = (request.GET.get("provedor") or "google").lower()
        caminho = PROVEDORES.get(provedor)

        if not caminho:
            return redirect(_deep_link(erro="provedor_invalido"))

        # Se já está logado no site pelo navegador, pula direto.
        if request.user.is_authenticated:
            return redirect("/api/v1/auth/app/token/")

        destino = "/api/v1/auth/app/token/"
        return redirect(f"{caminho}?process=login&next={destino}")


class AppTokenSocial(View):
    """GET /api/v1/auth/app/token/ -- fim do fluxo, devolve pro app."""

    def get(self, request):
        if not request.user.is_authenticated:
            return redirect(_deep_link(erro="nao_autenticado"))

        if not request.user.is_active:
            return redirect(_deep_link(erro="conta_desativada"))

        token, _ = Token.objects.get_or_create(user=request.user)
        perfil = getattr(request.user, "perfil", None)

        nome = (
            getattr(perfil, "nome_completo", "")
            or request.user.get_full_name()
            or request.user.username
        )

        return redirect(
            _deep_link(
                token=token.key,
                nome=nome,
                email=request.user.email or "",
            )
        )