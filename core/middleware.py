import logging
import os
import time
import uuid
from urllib.parse import urlencode

from django.db import InterfaceError, OperationalError, close_old_connections
from django.shortcuts import redirect
from django.urls import reverse


logger_performance = logging.getLogger("lazer.performance")
logger_bandwidth = logging.getLogger("lazer.bandwidth")


class BandwidthEconomyMiddleware:
    """Reduz respostas inúteis e deixa o consumo de bytes auditável.

    O antigo WordPress criou milhares de combinações ``filter_cat`` que
    crawlers continuam visitando. O catálogo atual não usa esse parâmetro:
    responder a página HTML completa para cada combinação apenas transfere
    bytes. A URL é consolidada em ``/loja/`` preservando apenas parâmetros
    conhecidos do catálogo.

    Respostas grandes também são registradas com o tamanho e a rota. Assim o
    painel do Render deixa de ser um total sem explicação e o log mostra o
    próximo alvo real de otimização.
    """

    PARAMETROS_CATALOGO = {
        "q", "categoria", "voltagem", "disponibilidade", "ordenar",
        "preco_min", "preco_max", "page",
    }
    LIMITE_LOG_PADRAO = 256 * 1024

    def __init__(self, get_response):
        self.get_response = get_response
        try:
            self.limite_log = max(
                16 * 1024,
                int(os.getenv("BANDWIDTH_LOG_MIN_BYTES", self.LIMITE_LOG_PADRAO)),
            )
        except (TypeError, ValueError):
            self.limite_log = self.LIMITE_LOG_PADRAO

    def __call__(self, request):
        resposta_curta = self._consolidar_filtro_legado(request)
        response = resposta_curta or self.get_response(request)
        self._registrar_resposta_grande(request, response)
        return response

    def _consolidar_filtro_legado(self, request):
        if request.method not in ("GET", "HEAD") or "filter_cat" not in request.GET:
            return None
        host = request.get_host().split(":", 1)[0].lower()
        if host.startswith("interno.") or request.path.startswith("/api/"):
            return None

        from django.http import HttpResponsePermanentRedirect

        pares = []
        for chave in self.PARAMETROS_CATALOGO:
            for valor in request.GET.getlist(chave):
                if valor:
                    pares.append((chave, valor[:120]))
        destino = "/loja/"
        if pares:
            destino += "?" + urlencode(pares)
        response = HttpResponsePermanentRedirect(destino)
        response["Cache-Control"] = "public, max-age=86400"
        response["X-Robots-Tag"] = "noindex, follow"
        return response

    def _registrar_resposta_grande(self, request, response):
        try:
            tamanho = int(response.get("Content-Length") or 0)
        except (TypeError, ValueError):
            tamanho = 0
        if tamanho >= self.limite_log:
            logger_bandwidth.warning(
                "large_response bytes=%s status=%s method=%s path=%s user_agent=%s",
                tamanho,
                response.status_code,
                request.method,
                request.path,
                (request.headers.get("User-Agent") or "-")[:160],
            )


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
        # O gatilho diz em QUAL cadastro o endereço já está (ver a
        # migração 0045). Cliente e conta de acesso podem repetir o
        # e-mail entre si -- o que a mensagem precisa explicar é a
        # duplicidade dentro do mesmo cadastro, que é o que foi barrado.
        falha = str(exception) if isinstance(exception, IntegrityError) else ""
        # Os índices únicos de e-mail das contas (contas/0003) e a guarda do
        # pre_save (contas/guarda.py) dizem o mesmo que o gatilho de conta.
        if "contas_auth_user_email_unico" in falha or "contas_emailaddress_email_unico" in falha:
            falha = "ls_email_duplicado_usuario"
        if "ls_email_duplicado" in falha:
            if "ls_email_duplicado_cliente" in falha:
                mensagem = (
                    "Este e-mail já está em outro cadastro de cliente. Volte ao "
                    "formulário e utilize o registro existente."
                )
            else:
                mensagem = (
                    "Este e-mail já está em outra conta de acesso. Volte ao "
                    "formulário e utilize a conta existente."
                )
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
        # As fotos e os arquivos públicos no banco (seção 130): iguais nos
        # dois endereços -- o painel mostra as mesmas fotos do site.
        "/midia/",
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

    STATUS_TRANSITORIOS = (502, 503, 504)

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
        # O ARQUIVO QUE NÃO FOI GUARDADO vira a janela de app, nunca 500
        # (seção 130): a tela que não trata o erro do armazenamento recebe o
        # mesmo JSON de ErroDeFormulario (msg, titulo), ou o recado no toast.
        from core.arquivos_no_banco import ArmazenamentoIndisponivel

        if isinstance(exception, ArmazenamentoIndisponivel):
            return self._arquivo_nao_guardado(request, exception)

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

    @staticmethod
    def _arquivo_nao_guardado(request, erro):
        from django.contrib import messages
        from django.http import JsonResponse
        from django.shortcuts import redirect
        from django.utils.http import url_has_allowed_host_and_scheme

        logger_performance.warning(
            "arquivo_nao_guardado id=%s method=%s path=%s",
            getattr(request, "ls_request_id", ""), request.method, request.path,
        )
        titulo = getattr(erro, "titulo", "") or "Arquivo não guardado"
        if (
            request.headers.get("X-Requested-With") in ("XMLHttpRequest", "LS-Soft-Navigation")
            or "application/json" in request.headers.get("Accept", "")
            or request.POST.get("resposta") == "json"
        ):
            corpo = {"status": "erro", "msg": str(erro), "titulo": titulo}
            if getattr(erro, "campo", ""):
                corpo["campo"] = erro.campo
            return JsonResponse(corpo, status=getattr(erro, "status", None) or 400)
        try:
            messages.error(request, str(erro), extra_tags=f"titulo:{titulo}")
        except Exception:  # noqa: BLE001 -- sem o MessageMiddleware o recado se perde, a tela não
            pass
        voltar = request.META.get("HTTP_REFERER") or ""
        if not url_has_allowed_host_and_scheme(voltar, allowed_hosts={request.get_host()}):
            voltar = "/"
        return redirect(voltar)


class TelefoneObrigatorioMiddleware:
    """Impede cliente autenticado sem telefone de navegar pelo site."""

    ROTAS_LIVRES = (
        "/completar-perfil/",
        "/logout/",
        "/accounts/",
        "/static/",
        "/media/",
        "/midia/",
        "/favicon.ico",
        "/system/",
        # Ligar o aviso no celular não é navegar pela loja: é um pedido
        # do próprio aparelho, muitas vezes de quem ainda nem completou
        # o cadastro. Redirecionar isto para "complete o perfil" devolve
        # HTML no meio de um `fetch` e a inscrição falha calada.
        "/aplicativo/",
        "/app-sw.js",
        # O token novo do CSRF (views_seguranca.py): é JSON pedido pelo fetch.
        "/seguranca/token/",
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


def e_da_equipe(user) -> bool:
    """Conta de acesso interno -- por função, por staff ou por superusuário.

    As três perguntas juntas de propósito: uma conta pode ter função de
    equipe sem `is_staff`, e o superusuário não precisa de função nenhuma
    para entrar em tudo. Qualquer uma delas basta para dizer "esta pessoa
    trabalha aqui".
    """
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
        return True

    from sistema_interno.permissoes import faz_parte_da_equipe

    return faz_parte_da_equipe(user)


class LojaSomenteDeClienteMiddleware:
    """Quem trabalha na fábrica não compra na própria loja.

    O QUE ACONTECIA. A conta da equipe é um `auth.User` como qualquer
    outra, então o site tratava um gerente como trata um cliente:
    carrinho, lista de desejos e "meus pedidos" apareciam para ele. Isso
    não é enfeite fora de lugar --

      * um pedido criado por conta interna entra na mesma fila de
        produção e no mesmo relatório de vendas da loja, e não é de
        cliente nenhum quando alguém pergunta quem comprou;
      * lista de desejos e carrinho da equipe se misturam aos indicadores
        de interesse do site, que existem para dizer o que os CLIENTES
        querem.

    A compra é do perfil de cliente. Para a equipe o site continua
    inteiro -- catálogo, peças, projetos, eventos, manutenção --, e a
    porta de volta é o painel.

    POR QUE MIDDLEWARE, E NÃO UM DECORADOR EM CADA VIEW. São mais de dez
    endereços entre carrinho, cupom, frete, pagamento e favoritos, e um
    deles esquecido é uma porta aberta que ninguém percebe. A lista
    abaixo é a regra inteira, num lugar só, fácil de conferir.
    """

    #: Tudo o que pertence à compra. Prefixo, porque cada um destes tem
    #: filhos (`/carrinho/adicionar/...`, `/pagamento/12/`).
    ROTAS_DE_COMPRA = (
        "/carrinho/",
        "/pagamento/",
        "/meus-pedidos/",
        "/lista-desejos/",
        "/favoritos/",
        "/salvar-cpf-carrinho/",
        "/calcular-frete/",
        "/api/pedido/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._pode_passar(request):
            return self.get_response(request)

        from django.contrib import messages
        from django.http import JsonResponse

        recado = (
            "Carrinho, lista de desejos e pedidos são do cliente. Sua conta "
            "é de acesso interno: use o painel da fábrica."
        )
        # Metade destes endereços é chamada por fetch, e um redirecionamento
        # ali volta como HTML no meio de um JSON.parse -- erro que aparece
        # na tela como "algo deu errado" e não explica nada.
        if request.headers.get("X-Requested-With") == "XMLHttpRequest" or (
            request.content_type and "application/json" in request.content_type
        ):
            return JsonResponse({"ok": False, "erro": recado}, status=403)

        messages.info(request, recado)
        return redirect("home")

    def _pode_passar(self, request):
        host = request.get_host().split(":", 1)[0].lower()
        if host.startswith("interno."):
            return True
        if not request.path.startswith(self.ROTAS_DE_COMPRA):
            return True

        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return True
        return not e_da_equipe(user)


class FotoReservaMiddleware:
    """Põe a reserva das fotos (site/ls-foto-reserva.js) nas páginas com fotos do Cloudinary.

    LEIA-ME-V10, seção 128; ver core/fotos_reserva.py. Um único ponto para
    o site, a gestão, o painel e as páginas públicas avulsas (assinatura,
    proposta, O.S.): toda página HTML que mostra foto do Cloudinary ganha o
    script, que só age se uma dessas fotos falhar. Página sem foto do
    Cloudinary sai como entrou.
    """

    MARCA = b"res.cloudinary.com"

    def __init__(self, get_response):
        self.get_response = get_response
        self._tag = None

    def tag(self):
        if self._tag is None:
            from django.templatetags.static import static

            versao = "1"
            try:
                from pathlib import Path

                arquivo = Path(__file__).resolve().parent / "static" / "site" / "ls-foto-reserva.js"
                versao = str(int(arquivo.stat().st_mtime))
            except OSError:
                pass
            self._tag = (
                f'<script src="{static("site/ls-foto-reserva.js")}?v={versao}" '
                f'data-indice="{static("site/fotos-reserva.json")}" defer></script>'
            ).encode()
        return self._tag

    def __call__(self, request):
        response = self.get_response(request)
        try:
            if (
                getattr(response, "streaming", False)
                or response.status_code != 200
                or "text/html" not in response.get("Content-Type", "")
                or response.get("Content-Encoding")
            ):
                return response
            conteudo = response.content
            if self.MARCA not in conteudo or b"ls-foto-reserva.js" in conteudo:
                return response
            posicao = conteudo.find(b"</head>")
            if posicao == -1:
                return response
            response.content = conteudo[:posicao] + self.tag() + conteudo[posicao:]
            if response.has_header("Content-Length"):
                response["Content-Length"] = str(len(response.content))
        except Exception:
            # a reserva nunca derruba a página
            return response
        return response
