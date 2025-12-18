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
