"""Configurações locais (desenvolvimento) — SQLite + Celery Eager para facilidade."""
import os

from .base import *  # noqa: F401,F403
from .base import DATABASES, INSTALLED_APPS

DEBUG = True

# Banco SQLite para desenvolvimento local rápido (sem dependência de Postgres).
DATABASES['default'] = {
    'ENGINE': 'django.db.backends.sqlite3',
    'NAME': BASE_DIR / 'db.sqlite3',
}

# Execução síncrona das tasks do Celery no desenvolvimento local, dispensando
# a necessidade de um worker/broker rodando. No production.py isto é desligado.
CELERY_TASK_ALWAYS_EAGER = os.environ.get('CELERY_TASK_ALWAYS_EAGER', '1') == '1'
