"""
Configuracao do projeto EV ChargeOps (Enterprise Challenge 2026, FIAP x GoodWe).

Sprint 2 -- implementacao da arquitetura definida na Sprint 1
(ver ../docs/frente-3-arquitetura.md).
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "django-insecure-dev-only-nao-usar-em-producao-troque-no-env",
)
DEBUG = os.getenv("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    # Apps do dominio. Apenas `core` define modelos: as 14 entidades da
    # Frente 3-C vivem juntas para que nenhuma FK atravesse fronteira de app.
    "core",
    "billing",
    "ingestion",
    "intelligence",
    "portal",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "chargeops.urls"

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
                "portal.context.perfil",
            ],
        },
    },
]

WSGI_APPLICATION = "chargeops.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME", "chargeops"),
        "USER": os.getenv("DB_USER", "chargeops"),
        "PASSWORD": os.getenv("DB_PASSWORD", "chargeops_dev"),
        "HOST": os.getenv("DB_HOST", "127.0.0.1"),
        "PORT": os.getenv("DB_PORT", "5432"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "pt-br"

# Persistencia em UTC (decisao da Frente 3-C: TIMESTAMPTZ armazenado em UTC).
# A apresentacao converte para o fuso do condominio -- ver core.timeutils.
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Fuso civil usado para decidir competencia de fatura e leitura de horarios.
# A regra de competencia da Opcao A e o *mes civil* do inicio da sessao, e mes
# civil so existe em fuso local: uma sessao iniciada 30/06 23:40 BRT e junho,
# mas em UTC ja seria 01/07.
CONDOMINIUM_TIME_ZONE = os.getenv("CONDOMINIUM_TIME_ZONE", "America/Sao_Paulo")

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"] if (BASE_DIR / "static").exists() else []

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "/entrar/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/entrar/"
