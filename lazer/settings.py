from pathlib import Path
import os

import cloudinary
import dj_database_url


# ============================================================
# BASE / AMBIENTE
# ============================================================
BASE_DIR = Path(__file__).resolve().parent.parent

IS_RENDER = os.getenv("RENDER", "").strip().lower() == "true"
IS_VERCEL = os.getenv("VERCEL", "").strip() == "1"

ENVIRONMENT = os.getenv(
    "ENVIRONMENT",
    "production" if IS_RENDER or IS_VERCEL else "development",
).strip().lower()

DEBUG = os.getenv(
    "DEBUG",
    "false" if ENVIRONMENT == "production" else "true",
).strip().lower() in ("1", "true", "yes", "on")

SECRET_KEY = os.getenv("SECRET_KEY", "").strip()
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "django-insecure-apenas-para-desenvolvimento-local"
    else:
        raise RuntimeError("SECRET_KEY não configurada no ambiente de produção.")


# ============================================================
# HOSTS / CSRF
# ============================================================
ALLOWED_HOSTS = [
    "lazerandsport.onrender.com",
    "lazersport.com.br",
    "www.lazersport.com.br",
    "interno.lazersport.com.br",
    ".vercel.app",
    ".onrender.com",
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
]

CSRF_TRUSTED_ORIGINS = [
    "https://lazerandsport.onrender.com",
    "https://lazersport.com.br",
    "https://www.lazersport.com.br",
    "https://interno.lazersport.com.br",
    "https://*.vercel.app",
    "https://*.onrender.com",
]

VERCEL_URL = os.getenv("VERCEL_URL", "").strip()
if VERCEL_URL:
    if VERCEL_URL not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(VERCEL_URL)
    vercel_origin = f"https://{VERCEL_URL}"
    if vercel_origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(vercel_origin)

extra_hosts = os.getenv("DJANGO_ALLOWED_HOSTS", "")
for host in extra_hosts.split(","):
    host = host.strip()
    if host and host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(host)

extra_origins = os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "")
for origin in extra_origins.split(","):
    origin = origin.strip().rstrip("/")
    if origin and origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(origin)


# ============================================================
# CLOUDINARY
# ============================================================
CLOUDINARY_STORAGE = {
    "CLOUD_NAME": (os.getenv("CLOUDINARY_CLOUD_NAME") or os.getenv("CLOUD_NAME") or "").strip(),
    "API_KEY": (os.getenv("CLOUDINARY_API_KEY") or os.getenv("CLOUD_API_KEY") or "").strip(),
    "API_SECRET": (os.getenv("CLOUDINARY_API_SECRET") or os.getenv("CLOUD_API_SECRET") or "").strip(),
}

if all(CLOUDINARY_STORAGE.values()):
    cloudinary.config(
        cloud_name=CLOUDINARY_STORAGE["CLOUD_NAME"],
        api_key=CLOUDINARY_STORAGE["API_KEY"],
        api_secret=CLOUDINARY_STORAGE["API_SECRET"],
        secure=True,
    )


# ============================================================
# APLICAÇÕES
# ============================================================
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Depois de staticfiles: o collectstatic nativo do Django/WhiteNoise prevalece
    # sobre o comando legado incluído pelo django-cloudinary-storage 0.3.0.
    "cloudinary_storage",
    "cloudinary",
    "django.contrib.humanize",
    "django.contrib.sites",

    # Aplicações internas
    "core",
    "sistema_interno",
    "cloud_jogos",

    # Terceiros
    "rest_framework",
    "django_filters",
    "mercadopago",
    "widget_tweaks",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "allauth.socialaccount.providers.facebook",
]

SITE_ID = 1


# ============================================================
# MIDDLEWARE
# ============================================================
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "core.middleware.SubdomainURLMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "lazer.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.categorias_globais",
                "core.context_processors.estabelecimentos_globais",
                "core.context_processors.manutencao_notificacao",
                "core.context_processors.carrinho_context",
                "core.context_processors.pedidos_ativos_context",
                "core.context_processors.admin_alertas_context",
                "sistema_interno.context_processors.fab_counts",
            ],
        },
    },
]

WSGI_APPLICATION = "lazer.wsgi.application"


# ============================================================
# BANCO ÚNICO: SUPABASE
# ============================================================
# Render, Vercel e execução local usam exatamente a mesma variável e o mesmo banco.
# Não existe fallback para Render ou SQLite: isso impede gravar dados no banco errado.
SUPABASE_DATABASE_URL = os.getenv("SUPABASE_DATABASE_URL", "").strip()

if not SUPABASE_DATABASE_URL:
    raise RuntimeError(
        "SUPABASE_DATABASE_URL não configurada. "
        "Cadastre a URI do Transaction Pooler do Supabase."
    )

DATABASES = {
    "default": dj_database_url.parse(
        SUPABASE_DATABASE_URL,
        conn_max_age=0,
        conn_health_checks=False,
        ssl_require=True,
    )
}

# O Transaction Pooler (porta 6543) não deve usar cursores mantidos no servidor.
DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True


# ============================================================
# AUTENTICAÇÃO
# ============================================================
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = True
ACCOUNT_AUTHENTICATION_METHOD = "username_email"
ACCOUNT_LOGOUT_ON_GET = True

LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# ============================================================
# INTERNACIONALIZAÇÃO
# ============================================================
LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True


# ============================================================
# STATIC / MEDIA
# ============================================================
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

STATICFILES_DIRS = []
if (BASE_DIR / "static").exists():
    STATICFILES_DIRS.append(BASE_DIR / "static")

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# STORAGES é a configuração atual compatível com Django 5.2.
# CompressedStaticFilesStorage evita erro de manifesto quando templates antigos
# apontam para algum arquivo estático que ainda não foi coletado.
#
# Antes, se faltasse qualquer variável do Cloudinary em produção, o Django
# caía em silêncio pro FileSystemStorage -- que não persiste nada na Vercel
# (sem disco) e não gerava nenhum erro, só imagem quebrada sem explicação.
# Agora isso quebra o deploy com uma mensagem clara dizendo o que falta.
_cloudinary_faltando = [nome for nome, valor in CLOUDINARY_STORAGE.items() if not valor]

if ENVIRONMENT == "production" and _cloudinary_faltando:
    raise RuntimeError(
        "Cloudinary não configurado em produção. Faltando: "
        f"{', '.join(_cloudinary_faltando)}. "
        "Confira essas variáveis de ambiente na Vercel."
    )

STORAGES = {
    "default": {
        "BACKEND": (
            "cloudinary_storage.storage.MediaCloudinaryStorage"
            if ENVIRONMENT == "production"
            else "django.core.files.storage.FileSystemStorage"
        )
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

# Compatibilidade com django-cloudinary-storage 0.3.0.
# O pacote ainda consulta estas configurações legadas durante collectstatic,
# mesmo no Django 5.2. Os arquivos estáticos continuam sendo servidos pelo
# WhiteNoise; apenas os uploads de mídia usam o Cloudinary em produção.
STATICFILES_STORAGE = "whitenoise.storage.CompressedStaticFilesStorage"
DEFAULT_FILE_STORAGE = STORAGES["default"]["BACKEND"]

WHITENOISE_AUTOREFRESH = DEBUG
WHITENOISE_USE_FINDERS = DEBUG


# ============================================================
# DJANGO REST FRAMEWORK
# ============================================================
REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
    ],
}


# ============================================================
# SEGURANÇA / COOKIES / PROXY HTTPS
# ============================================================
SESSION_COOKIE_SECURE = ENVIRONMENT == "production"
CSRF_COOKIE_SECURE = ENVIRONMENT == "production"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Opcional. Configure COOKIE_DOMAIN=.lazersport.com.br somente quando estiver
# usando o domínio próprio. Não configure durante testes em *.vercel.app.
COOKIE_DOMAIN = os.getenv("COOKIE_DOMAIN", "").strip()
if COOKIE_DOMAIN:
    SESSION_COOKIE_DOMAIN = COOKIE_DOMAIN
    CSRF_COOKIE_DOMAIN = COOKIE_DOMAIN


# ============================================================
# MERCADO PAGO / DEMAIS CONFIGURAÇÕES
# ============================================================
MP_ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN", "").strip()

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ============================================================
# LOGS DE ERRO NO RENDER E NA VERCEL
# ============================================================
# Garante que a exceção real de um HTTP 500 apareça nos logs da hospedagem.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
        "django.db.backends": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}