from django.conf import settings
from django.shortcuts import render

from django.http import HttpResponseServerError


from django.urls import set_urlconf

class SubdomainURLMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        if path.startswith(('/media/', '/static/', '/favicon.ico', '/system/')):
            return self.get_response(request)

        host = request.get_host().split(':')[0]

        if host.startswith('interno.'):
            request.is_interno = True
            set_urlconf('lazer.urls_interno')
        else:
            request.is_interno = False
            set_urlconf('core.urls')

        return self.get_response(request)

