"""Configuração do projeto.

Banco, em ordem de prioridade:
1. DATABASE_URL (Postgres gerenciado, ex.: Neon pelo marketplace da Vercel);
2. POSTGRES_HOST (docker-compose);
3. SQLite, só para testes locais rápidos.
"""
import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-inseguro-troque-em-producao")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",")

# A Vercel define VERCEL=1 nas funções. Lá o disco é somente leitura, exceto /tmp.
EM_SERVERLESS = os.environ.get("VERCEL") == "1"

# Atrás do proxy HTTPS da Vercel. Necessário para o admin (login por formulário) funcionar.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]
if os.environ.get("VERCEL_URL"):
    CSRF_TRUSTED_ORIGINS.append(f"https://{os.environ['VERCEL_URL']}")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "catalogo",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

URL_BANCO = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")
if URL_BANCO:
    _local = any(h in URL_BANCO for h in ("@localhost", "@127.0.0.1", "@db:"))
    DATABASES = {"default": dj_database_url.parse(URL_BANCO, conn_max_age=0, ssl_require=not _local)}
    # A URL padrão do Neon passa por um pool (PgBouncer em modo transação), que não suporta cursores
    # do lado do servidor. Desligá-los evita erros intermitentes em consultas grandes.
    DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True
elif os.environ.get("POSTGRES_HOST"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "HOST": os.environ["POSTGRES_HOST"],
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
            "NAME": os.environ.get("POSTGRES_DB", "cotador"),
            "USER": os.environ.get("POSTGRES_USER", "cotador"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "cotador"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT", "/tmp/media" if EM_SERVERLESS else BASE_DIR / "media"))

# Originais também guardados no banco. Necessário no deploy serverless de demonstração,
# onde o disco não persiste. Em produção, o lugar dos originais é o S3 (ver docs/01-proposta.md, 5.2).
ORIGINAIS_NO_BANCO = os.environ.get("ORIGINAIS_NO_BANCO", "1" if EM_SERVERLESS else "0") == "1"

# Permite o botão "Reiniciar demonstração" (apaga tudo e recria o cenário fictício).
DEMO_PERMITE_REINICIAR = os.environ.get("DEMO_PERMITE_REINICIAR", "1" if DEBUG else "0") == "1"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CORS_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if o.strip()
]
# Opcional: expressão para liberar as URLs de preview da Vercel, ex.: ^https://cotador-.*\.vercel\.app$
CORS_ALLOWED_ORIGIN_REGEXES = [r for r in [os.environ.get("CORS_ALLOWED_ORIGIN_REGEX", "")] if r]

REST_FRAMEWORK = {
    # MVP: sem autenticação para facilitar a demonstração. Ver docs/01-proposta.md (5.5 Segurança).
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_AUTHENTICATION_CLASSES": [],
}

# Extração: "deterministico" (padrão, sem custo, sem chave) ou "llm".
EXTRATOR_PADRAO = os.environ.get("EXTRATOR_PADRAO", "deterministico")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "claude-sonnet-5-5")

# Variação percentual entre versões acima da qual a validação emite alerta.
LIMITE_VARIACAO_ALERTA = float(os.environ.get("LIMITE_VARIACAO_ALERTA", "25"))

# Limites de comercialização em torno do valor comercial da NTRP: 30% acima e 30% abaixo.
# O piso real é o maior entre -30% e a despesa assistencial estimada; o protótipo usa só os 30%.
BANDA_ANS_PCT = float(os.environ.get("BANDA_ANS_PCT", "30"))
# Tolerância para comparar o padrão entre faixas da tabela de venda com o da NTRP (arredondamento).
TOLERANCIA_PADRAO_FAIXAS_PCT = float(os.environ.get("TOLERANCIA_PADRAO_FAIXAS_PCT", "1"))
