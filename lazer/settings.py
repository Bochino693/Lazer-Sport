from pathlib import Path
import os
import dj_database_url
from environ import Env
import cloudinary

# ------------------------------
# Environment
# ------------------------------
env = Env()
Env.read_env()

ENVIRONMENT = env('ENVIRONMENT', default="development")  # development ou production
CLOUD_NAME = env('CLOUD_NAME', default="dgikjmki8")

print("ENV:", ENVIRONMENT)
print("CLOUD:", CLOUD_NAME)

# ------------------------------
# Base settings
# ------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
DEBUG = ENVIRONMENT != "production"

ALLOWED_HOSTS = [
    "lazerandsport.onrender.com",
    "lazersport.com.br",
    "www.lazersport.com.br",
    "interno.lazersport.com.br",
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
]

# ------------------------------
# Applications
# ------------------------------
INSTALLED_APPS = [
    # Django
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'cloudinary_storage',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'django.contrib.sites',
    'cloudinary',

    # Apps internas
    'core',
    'sistema_interno',
    'cloud_jogos',

    # Terceiros
    'rest_framework',
    'mercadopago',
    'widget_tweaks',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.facebook',

]

SITE_ID = 1

# ------------------------------
# Middleware
# ------------------------------
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'core.middleware.SubdomainURLMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'lazer.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': ['templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.categorias_globais',
                'core.context_processors.estabelecimentos_globais',
                'core.context_processors.manutencao_notificacao',
                'core.context_processors.carrinho_context',
                'core.context_processors.pedidos_ativos_context',
                'core.context_processors.admin_alertas_context',
                'sistema_interno.context_processors.fab_counts',
            ],
        },
    },
]

WSGI_APPLICATION = 'lazer.wsgi.application'

# ------------------------------
# Database
# ------------------------------
if ENVIRONMENT == "production":
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': 'lazer_db_3a61',
            'USER': 'lazer_db_user',
            'PASSWORD': 'Q87NOM8DmALIGK4KfvPU0sEDL6NYEHmv',
            'HOST': 'dpg-d6jeqhnkijhs739fnol0-a.oregon-postgres.render.com',
            'PORT': '5432',
            'OPTIONS': {
                'sslmode': 'require',
            },
        }
    }
else:
    # Local (SQLite)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# ------------------------------
# Authentication
# ------------------------------
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = True
ACCOUNT_AUTHENTICATION_METHOD = 'username_email'
ACCOUNT_LOGOUT_ON_GET = True
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

# ------------------------------
# Password validation
# ------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ------------------------------
# Internationalization
# ------------------------------
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

# ------------------------------
# Static / Media
# ------------------------------
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# 1. Use o dicionário, não o cloudinary.config
CLOUDINARY_STORAGE = {
    'CLOUD_NAME': 'dgikjmki8',
    'API_KEY': '318428596175492',
    'API_SECRET': 'nvL7BaJZQ-K2mxmTqpzuhxyzyHQ',
}

# 2. Em produção, force o storage
if ENVIRONMENT == "production":
    DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'
    # Importante: Não mude o MEDIA_URL para o link do cloudinary aqui.
    # Deixe como '/media/', o CloudinaryStorage vai sobrescrever isso automaticamente.
    MEDIA_URL = '/media/'


# ------------------------------
# Django REST Framework
# ------------------------------
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.AllowAny'],
    'DEFAULT_FILTER_BACKENDS': ['django_filters.rest_framework.DjangoFilterBackend'],
}

# ------------------------------
# Misc
# ------------------------------
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
WHITENOISE_AUTOREFRESH = DEBUG
WHITENOISE_USE_FINDERS = True

# ------------------------------
# MercadoPago
# ------------------------------
MP_ACCESS_TOKEN = "APP_USR-8795517953113951-030313-7940e925097a2e9fb486d62a5f75e420-149578645"
SESSION_COOKIE_DOMAIN = ".lazersport.com.br"
CSRF_COOKIE_DOMAIN = ".lazersport.com.br"