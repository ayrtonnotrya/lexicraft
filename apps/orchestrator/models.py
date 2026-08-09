"""Modelos da app `orchestrator` — Execuções, Snapshots e Resultados dos Corretores.

Fonte da verdade: docs/DATABASE_SCHEMA.md (Sessão 3.3).
"""
from django.conf import settings
from django.db import models

from apps.core.choices import AuditorType, TaskStatus
from apps.core.models import TimeStampedModel
from apps.profiles.models import ProfileConfig


class TaskExecution(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='lexicraft_tasks',
    )
    profile = models.ForeignKey(
        ProfileConfig,
        on_delete=models.PROTECT,
        related_name='executions',
    )
    status = models.CharField(
        max_length=50, choices=TaskStatus.choices, default=TaskStatus.PENDING
    )

    # Modelo de LLM escolhido no momento da criação. É um snapshot desacoplado
    # do perfil: o usuário pode escolher qualquer modelo do catálogo, e a task
    # roda sempre com este valor (nunca com o default do perfil). Fallback:
    # quando o form não envia modelo, usa o model_name do perfil.
    model_name = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="ID do modelo escolhido para esta execução (desacoplado do perfil).",
    )

    # Entradas e Progresso
    original_prompt = models.TextField(help_text="Mensagem inicial do usuário")
    current_iteration = models.PositiveSmallIntegerField(default=1)
    current_step = models.CharField(
        max_length=255, blank=True, null=True, help_text="Progresso descritivo para HTMX"
    )
    started_at = models.DateTimeField(
        blank=True, null=True,
        help_text="Timestamp exato em que a task mudou de PENDING para RUNNING.",
    )
    last_heartbeat_at = models.DateTimeField(
        blank=True, null=True,
        help_text="Último sinal de vida do Worker. Atualizado a cada transição de step.",
    )

    # Limites (Teto de Recursos copiado do Perfil no momento da criação)
    max_iterations = models.PositiveSmallIntegerField(default=3)
    max_budget_usd = models.DecimalField(max_digits=8, decimal_places=4)
    max_time_seconds = models.PositiveIntegerField(
        help_text="Tempo limite copiado do perfil no momento da criação"
    )

    # Consumo de Isocusto (Tokens e Moeda)
    accumulated_prompt_tokens = models.PositiveIntegerField(default=0)
    accumulated_completion_tokens = models.PositiveIntegerField(default=0)
    accumulated_cost_usd = models.DecimalField(max_digits=10, decimal_places=6, default=0.0)

    # Resultado Final (Após Sucesso ou Rollback)
    final_text = models.TextField(blank=True, null=True)
    final_score = models.FloatField(
        blank=True, null=True, help_text="Pontuação Global W(x) atingida"
    )

    class Meta:
        verbose_name = "Execução de Tarefa"
        verbose_name_plural = "Execuções de Tarefa"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(accumulated_cost_usd__gte=0.0),
                name='check_task_cost_non_negative',
            )
        ]

    def __str__(self) -> str:
        return f"Task #{self.pk} - {self.user.username} ({self.status})"


class ExecutionSnapshot(TimeStampedModel):
    task_execution = models.ForeignKey(
        TaskExecution,
        on_delete=models.CASCADE,
        related_name='snapshots',
    )
    iteration_number = models.PositiveSmallIntegerField()
    generated_text = models.TextField()

    # O produto final W(x) do Motor de Nash
    nash_score = models.FloatField(help_text="Score Global consolidado [0.01, 1.0]")

    # Dict das notas rigorosas S_i por critério: {"axis_id": 0.85, ...}
    normalized_scores = models.JSONField(default=dict)

    # Custo isolado desse ciclo exato para métricas marginais
    cycle_cost_usd = models.DecimalField(max_digits=8, decimal_places=6, default=0.0)

    class Meta:
        verbose_name = "Snapshot de Iteração"
        verbose_name_plural = "Snapshots de Iteração"
        indexes = [
            # CRÍTICO: Indexação para a query de Rollback (order_by('-nash_score'))
            models.Index(fields=['task_execution', '-nash_score'], name='idx_rollback_optim'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['task_execution', 'iteration_number'],
                name='unique_iteration_per_task',
            )
        ]

    def __str__(self) -> str:
        return f"Snapshot Iteração {self.iteration_number} (W={self.nash_score:.4f})"


class AuditorResult(TimeStampedModel):
    snapshot = models.ForeignKey(
        ExecutionSnapshot,
        on_delete=models.CASCADE,
        related_name='auditor_results',
    )
    auditor_type = models.CharField(max_length=50, choices=AuditorType.choices)

    # Serialização validada do `AuditorResponseSchema` (Pydantic)
    deductions_payload = models.JSONField(
        help_text="Estrutura Pydantic com justificativas e deduções brutas do Corretor.",
    )

    class Meta:
        verbose_name = "Resultado do Corretor"
        verbose_name_plural = "Resultados dos Corretores"
        constraints = [
            models.UniqueConstraint(
                fields=['snapshot', 'auditor_type'],
                name='unique_auditor_per_snapshot',
            )
        ]

    def __str__(self) -> str:
        return f"{self.get_auditor_type_display()} - Snapshot #{self.snapshot.pk}"
