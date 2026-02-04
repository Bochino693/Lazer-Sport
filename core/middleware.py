from django.conf import settings
from django.shortcuts import render

from django.http import HttpResponseServerError

class GlobalExceptionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            return self.get_response(request)
        except Exception as e:
            if settings.DEBUG:
                raise  # 🔥 deixa o Django mostrar o erro real
            return render(request, "500.html", status=500)

class SubdomainURLMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        # 🔥 LIBERA MEDIA, STATIC, FAVICON E SYSTEM
        if (
            path.startswith('/media/')
            or path.startswith('/static/')
            or path.startswith('/favicon.ico')
            or path.startswith('/system/')
        ):
            return self.get_response(request)

        host = request.get_host().split(':')[0]

        if host.startswith('interno.'):
            request.is_interno = True
            request.urlconf = 'lazer.urls_interno'
        else:
            request.is_interno = False
            request.urlconf = 'core.urls'

        return self.get_response(request)

