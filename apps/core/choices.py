"""Enums/TextChoices globais do LexiCraft — ciclo de vida das tasks e papéis dos agentes.

Fonte da verdade: docs/DATABASE_SCHEMA.md (Sessão 2).
"""
from django.db import models
from django.utils.translation import gettext_lazy as _


class TaskStatus(models.TextChoices):
    PENDING = 'PENDING', _('Pendente')
    RUNNING = 'RUNNING', _('Em Execução')
    COMPLETED = 'COMPLETED', _('Concluído com Sucesso')
    COMPLETED_WITH_ROLLBACK = 'COMPLETED_WITH_ROLLBACK', _('Concluído com Rollback (Melhor Snapshot)')
    ABORTED_GUARDRAIL_STRIKES = 'ABORTED_GUARDRAIL_STRIKES', _('Abortado - Falha Crítica Guard-rail (3 Strikes)')
    FAILED_BUDGET_EXCEEDED = 'FAILED_BUDGET_EXCEEDED', _('Falha - Orçamento Excedido')
    FAILED_TIMEOUT = 'FAILED_TIMEOUT', _('Falha - Tempo Limite Excedido')
    FAILED_NO_SNAPSHOTS = 'FAILED_NO_SNAPSHOTS', _('Falha - Estagnado sem Snapshots')
    CANCELLED = 'CANCELLED', _('Cancelado pelo Usuário')


class PromptRole(models.TextChoices):
    WRITER = 'WRITER', _('Agente Redator')
    GUARDRAIL = 'GUARDRAIL', _('Agente Guard-rail (Fidelidade)')
    AUDITOR = 'AUDITOR', _('Corretor Base (Tribunal)')


class AuditorType(models.TextChoices):
    CORRETOR_1 = 'CORRETOR_1', _('Corretor Paralelo 1')
    CORRETOR_2 = 'CORRETOR_2', _('Corretor Paralelo 2')
    DESEMPATE = 'DESEMPATE', _('Corretor de Desempate (3º)')
