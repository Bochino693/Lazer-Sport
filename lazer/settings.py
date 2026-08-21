from pathlib import Path
import os

import cloudinary
import dj_database_url
from dotenv import load_dotenv


# ============================================================
# BASE / AMBIENTE
# ============================================================
BASE_DIR = Path(__file__).resolve().parent.parent

# Carrega o .env em desenvolvimento local. Em producao (Render/Vercel) as
# variaveis vem da plataforma e este arquivo nao existe -- load_dotenv
# simplesmente nao faz nada, sem erro.
# override=False: variavel ja definida no ambiente real tem prioridade
# sobre o .env, entao o deploy nunca e sobrescrito por um arquivo local.
load_dotenv(BASE_DIR / ".env", override=False)

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
    # Domínio .com: o painel interno atende em interno.lazersport.com.
    "lazersport.com",
    "www.lazersport.com",
    "interno.lazersport.com",
    ".vercel.app",
    ".onrender.com",
    "localhost",
    # Em desenvolvimento, http://interno.localhost:8000 cai no
    # SubdomainURLMiddleware e abre o painel interno sem precisar de
    # DNS nem de arquivo hosts -- navegador resolve *.localhost sozinho.
    ".localhost",
    "127.0.0.1",
    "0.0.0.0",
]

CSRF_TRUSTED_ORIGINS = [
    "https://lazerandsport.onrender.com",
    "https://lazersport.com.br",
    "https://www.lazersport.com.br",
    "https://interno.lazersport.com.br",
    "https://lazersport.com",
    "https://www.lazersport.com",
    "https://interno.lazersport.com",
    "https://*.vercel.app",
    "https://*.onrender.com",
    "http://interno.localhost:8000",
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
    # Sem isso, a lib usa MEDIA_URL ("/media/") como prefixo automático ao
    # montar a URL de leitura -- mas os public_id reais no Cloudinary NAO
    # tem esse prefixo, o que gerava 404 em toda imagem. Ver storage.py
    # (_prepend_prefix) e app_settings.py (PREFIX = ...MEDIA_URL) da lib
    # django-cloudinary-storage.
    "PREFIX": "",
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
    "django.contrib.sitemaps",

    # Aplicações internas
    "core",
    "sistema_interno",
    "cloud_jogos",

    # Terceiros
    "rest_framework",
    "rest_framework.authtoken",
    "django_filters",
    "mercadopago",
    "widget_tweaks",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "allauth.socialaccount.providers.apple",
]

SITE_ID = 1


# ============================================================
# MIDDLEWARE
# ============================================================
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.gzip.GZipMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "core.middleware.SubdomainURLMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "core.middleware.TelefoneObrigatorioMiddleware",
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
                "core.context_processors.clientes_rodape",
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
        "No Render, cadastre a URI do Session Pooler do Supabase (porta 5432). "
        "Em desenvolvimento, crie um arquivo .env na raiz do projeto "
        "(ao lado do manage.py) com SUPABASE_DATABASE_URL=postgresql://..."
    )

# O processo persistente do Render pode reaproveitar conexões. Isso evita um
# novo handshake TLS com o Supabase em cada consulta sem manter conexões por
# tempo demais. O valor ainda pode ser ajustado pela variável de ambiente.
try:
    DB_CONN_MAX_AGE = max(
        0,
        int(os.getenv("DB_CONN_MAX_AGE", "60" if IS_RENDER else "0")),
    )
except ValueError:
    DB_CONN_MAX_AGE = 60 if IS_RENDER else 0

DATABASES = {
    "default": dj_database_url.parse(
        SUPABASE_DATABASE_URL,
        conn_max_age=DB_CONN_MAX_AGE,
        conn_health_checks=DB_CONN_MAX_AGE > 0,
        ssl_require=True,
    )
}

# Compatível com os poolers do Supabase e evita estado de cursor entre conexões.
DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True


# ============================================================
# AUTENTICAÇÃO
# ============================================================
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

ACCOUNT_ADAPTER = "core.adapters.AccountAdapter"
SOCIALACCOUNT_ADAPTER = "core.adapters.SocialAccountAdapter"

# Sintaxe do allauth 65 (substitui ACCOUNT_EMAIL_REQUIRED,
# ACCOUNT_USERNAME_REQUIRED e ACCOUNT_AUTHENTICATION_METHOD).
ACCOUNT_LOGIN_METHODS = {"username", "email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "username*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_LOGOUT_ON_GET = True
ACCOUNT_UNIQUE_EMAIL = True

# O coração do "poupar o usuário de digitar": com AUTO_SIGNUP ligado, o
# allauth cria a conta direto com o que o Google/Apple mandou, sem passar
# pela tela de signup intermediária.
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_EMAIL_VERIFICATION = "none"
SOCIALACCOUNT_STORE_TOKENS = False
SOCIALACCOUNT_LOGIN_ON_GET = False  # exige POST no botão -- ver observação

LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

# ---------- Provedores ----------
# As credenciais vêm de variável de ambiente, não do admin. Assim o
# deploy na Vercel/Render não depende de cadastrar SocialApp no banco.
# IMPORTANTE: se você configurar aqui, NÃO crie também um SocialApp em
# /system/ -- o allauth levanta MultipleObjectsReturned se achar os dois.
SOCIALACCOUNT_PROVIDERS = {}

_GOOGLE_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()
_GOOGLE_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()

if _GOOGLE_ID and _GOOGLE_SECRET:
    SOCIALACCOUNT_PROVIDERS["google"] = {
        "APPS": [{
            "client_id": _GOOGLE_ID,
            "secret": _GOOGLE_SECRET,
            "key": "",
        }],
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
        "OAUTH_PKCE_ENABLED": True,
        "EMAIL_AUTHENTICATION": True,
    }

_APPLE_CLIENT_ID = os.getenv("APPLE_CLIENT_ID", "").strip()   # Services ID
_APPLE_KEY_ID = os.getenv("APPLE_KEY_ID", "").strip()         # Key ID
_APPLE_TEAM_ID = os.getenv("APPLE_TEAM_ID", "").strip()       # Team ID
_APPLE_PRIVATE_KEY = os.getenv("APPLE_PRIVATE_KEY", "").strip()

if _APPLE_CLIENT_ID and _APPLE_KEY_ID and _APPLE_TEAM_ID and _APPLE_PRIVATE_KEY:
    SOCIALACCOUNT_PROVIDERS["apple"] = {
        "APPS": [{
            "client_id": _APPLE_CLIENT_ID,
            "secret": _APPLE_KEY_ID,
            "key": _APPLE_TEAM_ID,
            "settings": {
                # A .p8 é multilinha. Em painel de env var, cole com \n
                # literal; esta linha desfaz o escape.
                "certificate_key": _APPLE_PRIVATE_KEY.replace("\\n", "\n"),
            },
        }],
        "EMAIL_AUTHENTICATION": True,
    }

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
_cloudinary_faltando = [
    nome for nome, valor in CLOUDINARY_STORAGE.items()
    if nome != "PREFIX" and not valor
]

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
try:
    WHITENOISE_MAX_AGE = max(60, int(os.getenv("STATIC_CACHE_MAX_AGE", "86400")))
except ValueError:
    WHITENOISE_MAX_AGE = 86400


# ============================================================
# DJANGO REST FRAMEWORK
# ============================================================
REST_FRAMEWORK = {
    # A ordem importa: TokenAuthentication PRIMEIRO. Sem ela declarada,
    # o DRF usa Session+Basic e ignora o header "Authorization: Token".
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
    ],
    # Em produção o app é o único cliente: a API navegável em HTML só
    # serve pra gastar CPU e vazar formulário. Fica só JSON.
    "DEFAULT_RENDERER_CLASSES": (
        ["rest_framework.renderers.JSONRenderer"]
        if not DEBUG
        else [
            "rest_framework.renderers.JSONRenderer",
            "rest_framework.renderers.BrowsableAPIRenderer",
        ]
    ),
    "UNAUTHENTICATED_USER": None,
}

# Deep link que devolve o token pro app depois do login social.
APP_DEEP_LINK = os.getenv("APP_DEEP_LINK", "lazersport://auth").strip()

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
MP_PUBLIC_KEY = os.getenv("MP_PUBLIC_KEY", "").strip()

# ============================================================
# E-MAIL (SMTP) -- usado pra avisar o cliente quando o status de
# uma manutenção muda. Sem essas variáveis configuradas no ambiente
# (Vercel/Render), o envio falha silenciosamente -- a tela mostra um
# aviso "não foi possível avisar o cliente", mas o status é
# atualizado normalmente mesmo assim.
#
# Exemplo pra Gmail: EMAIL_HOST_USER é o e-mail completo
# (algo@gmail.com) e EMAIL_HOST_PASSWORD é uma "senha de app" gerada
# em myaccount.google.com/apppasswords -- NÃO é a senha normal da
# conta, e só existe depois de ativar a verificação em duas etapas.
# Qualquer outro provedor SMTP (Brevo, Mailgun, Resend, Zoho, etc.)
# funciona trocando EMAIL_HOST/EMAIL_PORT e as credenciais.
# ============================================================
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com").strip()
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587").strip() or "587")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "true").strip().lower() == "true"
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "false").strip().lower() == "true"
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "").strip()
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "").strip()
DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL",
    EMAIL_HOST_USER or "nao-responda@lazersport.com.br",
).strip()
# Timeout curto: numa função serverless, é melhor a notificação falhar
# rápido (e cair no aviso "não foi possível avisar") do que travar a
# resposta inteira esperando um SMTP fora do ar.
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "10").strip() or "10")

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

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "lazersport",
    }
}

# A Home usa somente dados públicos nesse cache. Carrinho, usuário e mensagens
# continuam fora dele. Como saves no catálogo invalidam a chave na hora, um TTL
# maior reduz consultas e tráfego no Supabase sem atrasar atualizações do admin.
try:
    HOME_CACHE_TTL = max(60, int(os.getenv("HOME_CACHE_TTL", "1800")))
except ValueError:
    HOME_CACHE_TTL = 1800

try:
    CATALOG_CACHE_TTL = max(60, int(os.getenv("CATALOG_CACHE_TTL", "1800")))
except ValueError:
    CATALOG_CACHE_TTL = 1800
