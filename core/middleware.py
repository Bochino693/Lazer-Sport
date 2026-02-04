from django.urls import set_urlconf
from django.conf import settings

class SubdomainURLMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host().split(':')[0].lower()
        path = request.path

        # 1. Ignorar arquivos estáticos e de sistema para não quebrar o carregamento
        if path.startswith(('/media/', '/static/', '/favicon.ico', '/system/')):
            return self.get_response(request)

        # 2. Lógica de Roteamento por Subdomínio
        if host.startswith('interno.'):
            request.is_interno = True
            # Certifique-se de que o arquivo sistema-interno/urls.py existe
            # Se a pasta tiver hífen, o Python usa underline: sistema_interno.urls
            set_urlconf('sistema_interno.urls')
        else:
            request.is_interno = False
            set_urlconf('core.urls')

        response = self.get_response(request)
        return response