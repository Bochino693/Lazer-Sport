
class SubdomainURLMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        host = request.get_host().split(':')[0].lower()

        # 1. Ignora rotas de sistema
        if path.startswith((
            '/static/',
            '/media/',
            '/favicon.ico',
            '/admin/',
        )):
            return self.get_response(request)

        # 2. Define urlconf por subdomínio
        if host.startswith('interno.'):
            request.urlconf = 'sistema_interno.urls'
            request.is_interno = True
        else:
            request.urlconf = 'lazer.urls'
            request.is_interno = False

        return self.get_response(request)
