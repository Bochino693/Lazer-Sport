class SubdomainURLMiddleware:
    """
    Direciona somente o subdomínio interno para o conjunto de URLs
    do sistema interno.

    O site público deve continuar usando ROOT_URLCONF = "lazer.urls",
    pois é nesse arquivo que ficam reunidas as URLs do django-allauth
    (/accounts/) e as URLs públicas do core.

    Não defina request.urlconf = "core.urls" para o domínio público:
    isso remove temporariamente as rotas google_login, apple_login,
    account_reset_password e demais rotas do allauth durante a requisição.
    """

    ROTAS_GLOBAIS = (
        "/static/",
        "/media/",
        "/favicon.ico",
        "/system/",
        "/accounts/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.is_interno = False

        host = request.get_host().split(":", 1)[0].lower()
        path = request.path

        # Essas rotas sempre usam o ROOT_URLCONF principal.
        if path.startswith(self.ROTAS_GLOBAIS):
            return self.get_response(request)

        # Somente o subdomínio interno recebe um URLConf alternativo.
        if host.startswith("interno."):
            request.urlconf = "sistema_interno.urls"
            request.is_interno = True

        # No domínio público não alteramos request.urlconf.
        # Assim o Django mantém lazer.urls, onde allauth.urls é incluído.
        return self.get_response(request)
