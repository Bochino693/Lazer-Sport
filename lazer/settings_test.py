"""Configuração isolada para testes locais e para o script PowerShell.

Nunca conecta ao Supabase: o banco existe somente em memória e é descartado
ao final do comando `manage.py test`.
"""

import os

os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("SUPABASE_DATABASE_URL", "sqlite:///ignorado.sqlite3")

from .settings import *  # noqa: E402,F401,F403


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}
DEFAULT_FILE_STORAGE = STORAGES["default"]["BACKEND"]

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]
EMAIL_BACKEND = "core.email_backend.EmailBackend"
EMAIL_TRANSPORT_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Os campos de imagem apontam para o Cloudinary direto no modelo, então o
# storage de teste não os alcança: montar a URL exigia cloud_name e o teste
# de galeria quebrava fora do servidor. Credencial falsa resolve -- montar
# URL é cálculo local, nenhuma chamada de rede acontece aqui.
import cloudinary  # noqa: E402

CLOUDINARY_STORAGE = {
    "CLOUD_NAME": "teste-local",
    "API_KEY": "000000000000000",
    "API_SECRET": "teste-local-sem-rede",
}

cloudinary.config(
    cloud_name=CLOUDINARY_STORAGE["CLOUD_NAME"],
    api_key=CLOUDINARY_STORAGE["API_KEY"],
    api_secret=CLOUDINARY_STORAGE["API_SECRET"],
    secure=True,
)


# ============================================================
# O PAINEL INTERNO MORA NUM SUBDOMÍNIO -- INCLUSIVE NOS TESTES
# ============================================================
# `SubdomainURLMiddleware` só resolve as rotas internas quando o host
# começa com "interno.", então todo teste do painel pede a página com
# HTTP_HOST="interno.testserver". O cliente de teste do Django libera
# "testserver" sozinho, mas não o subdomínio: sem esta linha, a resposta
# volta 400 (DisallowedHost) em HTML, e o teste falha dizendo
# "400 != 403" ou "Content-Type não é application/json" -- mensagem que
# não tem nada a ver com o que se está testando.
#
# Ficava resolvido caso a caso, com @override_settings em cada classe.
# Quem escrevia a classe seguinte esquecia, e a falha voltava disfarçada
# de bug de permissão. Aqui vale para a suíte inteira.
#
# A lista de produção continua valendo (os testes do cartão público
# pedem a página por "lazersport.onrender.com"); aqui só se acrescenta
# o que o cliente de teste usa.
for _host_de_teste in ("testserver", "interno.testserver", ".testserver"):
    if _host_de_teste not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(_host_de_teste)
