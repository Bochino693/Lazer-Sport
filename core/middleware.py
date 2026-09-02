import logging
import os
import time
import uuid

from django.db import InterfaceError, OperationalError, close_old_connections
from django.shortcuts import redirect
from django.urls import reverse


logger_performance = logging.getLogger("lazer.performance")


class RequestTimingMiddleware:
    """Expõe e registra requisições lentas antes que virem um 502 opaco."""

    def __init__(self, get_response):
        self.get_response = get_response
        try:
            self.limite_ms = max(250, int(os.getenv("SLOW_REQUEST_MS", "1800")))
        except ValueError:
            self.limite_ms = 1800

    def __call__(self, request):
        inicio = time.perf_counter()
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        request.ls_request_id = request_id
        try:
            response = self.get_response(request)
        except Exception:
            duracao = round((time.perf_counter() - inicio) * 1000)
            logger_performance.exception(
                "request_failed id=%s method=%s path=%s duration_ms=%s",
                request_id,
                request.method,
                request.path,
                duracao,
            )
            raise

        duracao = round((time.perf_counter() - inicio) * 1000)
        response["X-Request-ID"] = request_id
        response["Server-Timing"] = f'app;dur={duracao}'
        if duracao >= self.limite_ms:
            logger_performance.warning(
                "slow_request id=%s method=%s path=%s status=%s duration_ms=%s",
                request_id,
                request.method,
                request.path,
                response.status_code,
                duracao,
            )
        return response

    def process_exception(self, request, exception):
        from django.db import IntegrityError
        from django.http import JsonResponse, HttpResponse
        if isinstance(exception, IntegrityError) and "ls_email_duplicado" in str(exception):
            mensagem = "Este e-mail já pertence a outro cadastro. Volte ao formulário e utilize o registro existente."
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"status": "erro", "msg": mensagem}, status=409)
            return HttpResponse(mensagem, status=409, content_type="text/plain; charset=utf-8")
        return None


class SubdomainURLMiddleware:
    #: Endereços que existem igual em qualquer host. Fora desta lista, um
    #: pedido para `interno.` só encontra o que `sistema_interno/urls.py`
    #: define -- e o que não estiver lá volta 404.
    ROTAS_GLOBAIS = (
        "/static/",
        "/media/",
        "/favicon.ico",
        "/system/",
        "/accounts/",
        "/healthz/",
        # `/pronto/` FALTAVA AQUI, E ISSO CUSTAVA CARO.
        #
        # Ele é quem acorda o processo E a conexão do banco antes de uma
        # gravação, e é chamado pelo navegador de quem está usando o
        # PAINEL -- ou seja, sempre pelo subdomínio `interno.`. Só que
        # ele mora em `core/urls.py`, e no subdomínio o urlconf é outro:
        # toda chamada voltava 404.
        #
        # O painel lê 404 como "o servidor não respondeu", então ele
        # concluía que a instância estava dormindo em TODA gravação feita
        # depois de dois minutos parado -- e pagava a escada de espera
        # inteira antes de mandar o POST, com o servidor de pé o tempo
        # todo. A tarja "Servidor acordando…" aparecia com o servidor
        # acordado.
        #
        # Ver `core.views.pronto` e `docs/RENDER_502.md`.
        "/pronto/",
        "/robots.txt",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.is_interno = False
        host = request.get_host().split(":", 1)[0].lower()
        path = request.path

        if path.startswith(self.ROTAS_GLOBAIS):
            return self.get_response(request)

        if host.startswith("interno."):
            request.urlconf = "sistema_interno.urls"
            request.is_interno = True

        return self.get_response(request)


class InternalResponseRecoveryMiddleware:
    """Transforma falhas opacas do painel em uma resposta recuperável.

    Não mascara erros do site público nem tenta repetir gravações. Respostas
    transitórias do painel ganham uma tela autossuficiente e um Retry-After;
    chamadas JavaScript recebem JSON para manter a tela que já estava aberta.
    """

    STATUS_TRANSITORIOS = (500, 502, 503, 504)

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if (
            getattr(request, "is_interno", False)
            and response.status_code in self.STATUS_TRANSITORIOS
        ):
            from sistema_interno.resiliencia import resposta_temporaria

            return resposta_temporaria(
                request,
                motivo=f"upstream-{response.status_code}",
            )
        return response

    def process_exception(self, request, exception):
        """Conexão remota quebrada vira recuperação, nunca página 500/502.

        Não repetimos a operação: um POST pode ter sido confirmado pelo
        banco antes de a conexão cair. Fechamos a conexão inutilizável para
        a próxima requisição nascer limpa e devolvemos uma resposta curta,
        sem context processors que dependam do mesmo banco.
        """
        if not getattr(request, "is_interno", False):
            return None
        if not isinstance(exception, (OperationalError, InterfaceError)):
            return None

        close_old_connections()
        logger_performance.warning(
            "database_connection_recovered id=%s method=%s path=%s error=%s",
            getattr(request, "ls_request_id", ""),
            request.method,
            request.path,
            exception.__class__.__name__,
        )
        from sistema_interno.resiliencia import resposta_temporaria

        return resposta_temporaria(request, motivo="banco-remoto")


class TelefoneObrigatorioMiddleware:
    """Impede cliente autenticado sem telefone de navegar pelo site."""

    ROTAS_LIVRES = (
        "/completar-perfil/",
        "/logout/",
        "/accounts/",
        "/static/",
        "/media/",
        "/favicon.ico",
        "/system/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        host = request.get_host().split(":", 1)[0].lower()

        if host.startswith("interno."):
            return self.get_response(request)

        if not user or not user.is_authenticated:
            return self.get_response(request)

        if user.is_staff or user.is_superuser:
            return self.get_response(request)

        if request.path.startswith(self.ROTAS_LIVRES):
            return self.get_response(request)

        perfil = getattr(user, "perfil", None)
        telefone = (getattr(perfil, "telefone", "") or "").strip()

        if not telefone:
            return redirect(f"{reverse('completar_perfil')}#telefone-box")

        return self.get_response(request)
