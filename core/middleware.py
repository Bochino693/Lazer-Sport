from django.shortcuts import render


class GlobalExceptionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            response = self.get_response(request)
            return response

        except Exception:
            # Captura QUALQUER erro inesperado
            return render(request, "500.html", status=500)


class SubdomainURLMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        # 🔥 LIBERA MEDIA E STATIC
        if (
            path.startswith('/media/')
            or path.startswith('/static/')
            or path.startswith('/favicon.ico')
        ):
            return self.get_response(request)

        host = request.get_host()

        # interno.lazersport.com.br
        if host.startswith('interno.'):
            request.is_interno = True
        else:
            request.is_interno = False

        return self.get_response(request)