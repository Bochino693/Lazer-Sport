from django.urls import set_urlconf
from django.conf import settings
import logging

# Opcional: para você ver no terminal quando a troca ocorrer
logger = logging.getLogger(__name__)


class SubdomainURLMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 1. Extrai o host (remove a porta se houver)
        host = request.get_host().split(':')[0].lower()
        path = request.path

        # 2. Ignorar arquivos estáticos e de sistema
        if path.startswith(('/media/', '/static/', '/favicon.ico', '/admin/')):
            return self.get_response(request)

        # 3. Define qual arquivo de URL usar
        # Use o caminho Python exato para o seu arquivo de urls do interno
        urlconf_interno = 'sistema_interno.urls'
        urlconf_core = settings.ROOT_URLCONF  # Pega o padrão (lazer.urls)

        if host.startswith('interno.'):
            request.is_interno = True
            urlconf = urlconf_interno
        else:
            request.is_interno = False
            urlconf = urlconf_core

        # 4. A MÁGICA: Força o Django a usar este arquivo para esta requisição
        request.urlconf = urlconf
        set_urlconf(urlconf)

        response = self.get_response(request)

        # 5. Limpa após a resposta para não vazar para a próxima requisição
        set_urlconf(None)

        return response

