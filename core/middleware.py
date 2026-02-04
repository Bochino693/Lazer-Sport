from django.urls import set_urlconf

class SubdomainURLMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.is_interno = False

        host = request.get_host().split(':')[0].lower()
        path = request.path

        # rotas que SEMPRE usam o core
        if path.startswith((
            '/static/',
            '/media/',
            '/favicon.ico',
            '/system/',
            '/accounts/',
        )):
            set_urlconf('lazer.urls')
            return self.get_response(request)

        if host.startswith('interno.'):
            set_urlconf('sistema_interno.urls')
            request.is_interno = True
        else:
            set_urlconf('core.urls')

        return self.get_response(request)