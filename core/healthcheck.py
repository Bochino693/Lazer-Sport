"""Liveness do processo WSGI, independente de sessões e banco.

Não verifica disponibilidade do banco: /pronto/ continua com essa função.
A sonda usa o mesmo worker do site, portanto ainda falha se ele travar.
"""


class HealthcheckWSGI:
    def __init__(self, application):
        self.application = application

    def __call__(self, environ, start_response):
        if (environ.get("PATH_INFO") in ("/healthz", "/healthz/")
                and environ.get("REQUEST_METHOD") in ("GET", "HEAD")):
            start_response("200 OK", [
                ("Content-Type", "text/plain; charset=utf-8"),
                ("Content-Length", "2"),
                ("Cache-Control", "no-store"),
            ])
            return [] if environ["REQUEST_METHOD"] == "HEAD" else [b"ok"]
        return self.application(environ, start_response)
