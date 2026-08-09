"""Modelos base e utilitários compartilhados da app `core`.

Fonte da verdade: docs/DATABASE_SCHEMA.md (Sessão 3.1).
"""
from django.db import models


class TimeStampedModel(models.Model):
    """Modelo abstrato para herança de rastreabilidade (created_at / updated_at)."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
