"""Configurações de produção — PostgreSQL + broker Redis real, DEBUG desligado."""
from .base import *  # noqa: F401,F403

DEBUG = False

# Em produção o worker real do Celery assume o broker Redis configurado em base.py.
CELERY_TASK_ALWAYS_EAGER = False
