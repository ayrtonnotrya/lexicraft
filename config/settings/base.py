"""
Settings base do LexiCraft — compartilhados entre ambientes local e produção.

Filosofia Monólito Majestoso: Django Templates + HTMX + Tailwind CSS.
Stack assíncrona: Celery + Redis para o loop agêntico; httpx para LLMs.
"""
import os
from pathlib import Path

from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ---------------------------------------------------------------------------
# Segurança
# ---------------------------------------------------------------------------
SECRET_KEY = config('SECRET_KEY', default='insecure-dev-key-change-me')
DEBUG = config('DEBUG', default=True, cast=bool)
ALLOWED_HOSTS = [h.strip() for h in config('ALLOWED_HOSTS', default='localhost,127.0.0.1').split(',') if h.strip()]

# ---------------------------------------------------------------------------
# Aplicações
# ---------------------------------------------------------------------------
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'django_htmx',
    'whitenoise.runserver_nostatic',
]

LOCAL_APPS = [
    'apps.core',
    'apps.profiles',
    'apps.orchestrator',
    'apps.dashboard',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_htmx.middleware.HtmxMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# ---------------------------------------------------------------------------
# Banco de Dados (PostgreSQL em produção; SQLite permitido para testes/dev)
# ---------------------------------------------------------------------------
def _default_db() -> dict:
    if os.environ.get('USE_SQLITE') == '1':
        return {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    return {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('POSTGRES_DB', default='lexicraft'),
        'USER': config('POSTGRES_USER', default='postgres'),
        'PASSWORD': config('POSTGRES_PASSWORD', default='postgres'),
        'HOST': config('POSTGRES_HOST', default='localhost'),
        'PORT': config('POSTGRES_PORT', default='5432'),
    }

DATABASES = {
    'default': _default_db(),
}

# ---------------------------------------------------------------------------
# Validação de senhas (Django defaults)
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ---------------------------------------------------------------------------
# Autenticação (login/logout próprios do monólito)
# ---------------------------------------------------------------------------
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard:dashboard_index'
LOGOUT_REDIRECT_URL = 'dashboard:dashboard_index'

# ---------------------------------------------------------------------------
# Internacionalização
# ---------------------------------------------------------------------------
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Arquivos estáticos
# ---------------------------------------------------------------------------
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ---------------------------------------------------------------------------
# Celery / Redis
# ---------------------------------------------------------------------------
REDIS_URL = config('REDIS_URL', default='redis://localhost:6379/0')
CELERY_BROKER_URL = config('CELERY_BROKER_URL', default=REDIS_URL)
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default=REDIS_URL)
CELERY_TASK_ALWAYS_EAGER = config('CELERY_TASK_ALWAYS_EAGER', default=False, cast=bool)
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TIMEZONE = TIME_ZONE
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# ---------------------------------------------------------------------------
# LLM / OpenCode Go (Universal JSON Mode, nunca strict/parse)
# ---------------------------------------------------------------------------
OPENAI_BASE_URL = config('OPENAI_BASE_URL', default='https://opencode.ai/zen/go/v1')
OPENAI_API_KEY = config('OPENAI_API_KEY', default='')
OPENCODE_MODELS_URL = config('OPENCODE_MODELS_URL', default='https://opencode.ai/zen/go/v1/models')
DEFAULT_MODEL_NAME = config('DEFAULT_MODEL_NAME', default='deepseek-v4-flash')

# Temperatura de amostragem das chamadas de LLM. Alguns modelos do catálogo
# (ex.: glm-5.2) só aceitam temperature=1 — um valor fixo baixo (0.0/0.7) faz a
# chamada falhar com 400. Usamos 1.0 como default seguro e universal, mantendo
# a capacidade de ajuste fino por ambiente.
LLM_TEMPERATURE = config('LLM_TEMPERATURE', default=1.0, cast=float)

# Tabela estática de custos (USD por 1M de tokens) — Motor de Isocusto.
COST_PER_1M_PROMPT_TOKENS = config('COST_PER_1M_PROMPT_TOKENS', default=0.15, cast=float)
COST_PER_1M_COMPLETION_TOKENS = config('COST_PER_1M_COMPLETION_TOKENS', default=0.60, cast=float)

# Limites globais de fallback do sistema.
MAX_BUDGET_USD_PER_TASK = config('MAX_BUDGET_USD_PER_TASK', default=2.50, cast=float)
MAX_TIME_SECONDS_PER_TASK = config('MAX_TIME_SECONDS_PER_TASK', default=300, cast=int)
MAX_ITERATIONS_PER_TASK = config('MAX_ITERATIONS_PER_TASK', default=3, cast=int)

# Alvo global de convergência W(x) e épsilon de estagnação (Delta W).
NASH_TARGET_SCORE = 0.95
NASH_EPSILON = 0.02

# Logging estruturado.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {'format': '[{asctime}] {levelname} {name} — {message}', 'style': '{'},
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'verbose'},
    },
    'root': {'handlers': ['console'], 'level': 'INFO'},
}
