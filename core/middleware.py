class SubdomainURLMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.is_interno = False

        host = request.get_host().split(':')[0].lower()
        path = request.path

        # caminhos que NÃO entram na lógica de subdomínio
        if path.startswith((
            '/static/',
            '/media/',
            '/favicon.ico',
            '/system/',
            '/accounts/',
        )):
            return self.get_response(request)

        if host.startswith('interno.'):
            request.urlconf = 'sistema_interno.urls'
            request.is_interno = True
        else:
            request.urlconf = 'core.urls'

        return self.get_response(request)


