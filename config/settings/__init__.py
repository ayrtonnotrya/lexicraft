"""Configurações do LexiCraft — carrega o módulo de settings ativo via DJANGO_SETTINGS_MODULE."""
from ..celery import app as celery_app

__all__ = ('celery_app',)
