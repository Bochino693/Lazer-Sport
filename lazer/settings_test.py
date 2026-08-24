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
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
