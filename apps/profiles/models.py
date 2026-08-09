"""Modelos da app `profiles` — Perfis de Geração, Eixos de Qualidade e Prompts.

Fonte da verdade: docs/DATABASE_SCHEMA.md (Sessão 3.2).
"""
from django.core.validators import MinValueValidator
from django.db import models

from apps.core.choices import PromptRole
from apps.core.models import TimeStampedModel


class ProfileConfig(TimeStampedModel):
    name = models.CharField(max_length=255, unique=True, verbose_name="Nome do Perfil")
    is_active = models.BooleanField(default=True, db_index=True)
    description = models.TextField(blank=True, null=True)

    # Modelo de LLM (OpenCode Go) utilizado por este Perfil.
    # As choices são populadas dinamicamente via https://opencode.ai/zen/go/v1/models
    # (ver service apps/orchestrator/services/model_catalog.py). Nada é hardcoded.
    model_name = models.CharField(
        max_length=100,
        default="deepseek-v4-flash",
        help_text="ID do modelo no catálogo OpenCode Go (fallback: deepseek-v4-flash).",
    )

    # Tetos padrão recomendados (Customizáveis por instância)
    default_max_iterations = models.PositiveSmallIntegerField(default=3)
    default_max_budget_usd = models.DecimalField(max_digits=6, decimal_places=4, default=2.50)
    default_max_time_seconds = models.PositiveIntegerField(
        default=300,
        help_text="Tempo máximo de execução em segundos (T_max)",
    )

    class Meta:
        verbose_name = "Perfil de Geração"
        verbose_name_plural = "Perfis de Geração"

    def __str__(self) -> str:
        return self.name


class QualityAxis(TimeStampedModel):
    profile = models.ForeignKey(ProfileConfig, on_delete=models.CASCADE, related_name='axes')
    name = models.CharField(max_length=150, verbose_name="Critério/Eixo")
    weight = models.FloatField(
        default=1.0,
        validators=[MinValueValidator(0.01)],
        help_text="Peso nominal. Será normalizado automaticamente (sum w_i = 1.0) no cálculo.",
    )
    base_score = models.FloatField(
        default=100.0,
        validators=[MinValueValidator(1.0)],
        help_text="Pontuação total do critério antes das deduções.",
    )
    deduction_rules = models.TextField(
        help_text="Subprompt injetado para o Corretor detalhando as regras de penalização.",
    )

    class Meta:
        verbose_name = "Eixo de Qualidade"
        verbose_name_plural = "Eixos de Qualidade"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(weight__gt=0),
                name='check_axis_weight_positive',
            ),
            models.CheckConstraint(
                condition=models.Q(base_score__gt=0),
                name='check_axis_base_score_positive',
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.profile.name})"


class SystemPrompt(TimeStampedModel):
    profile = models.ForeignKey(ProfileConfig, on_delete=models.CASCADE, related_name='prompts')
    role_type = models.CharField(max_length=50, choices=PromptRole.choices)
    content = models.TextField(help_text="Diretriz de sistema principal do Agente.")

    class Meta:
        verbose_name = "Prompt do Sistema"
        verbose_name_plural = "Prompts do Sistema"
        constraints = [
            models.UniqueConstraint(
                fields=['profile', 'role_type'],
                name='unique_role_per_profile',
            )
        ]

    def __str__(self) -> str:
        return f"{self.get_role_type_display()} - {self.profile.name}"
