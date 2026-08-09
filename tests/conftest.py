"""Fixtures pytest compartilhadas — Zero Network garantido."""
import pytest
from django.contrib.auth import get_user_model

from apps.core.choices import PromptRole
from apps.orchestrator.models import TaskExecution
from apps.profiles.models import ProfileConfig, QualityAxis, SystemPrompt

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="tester", password="testpass123")


@pytest.fixture
def profile(db):
    """Perfil ativo com 2 eixos (PKs 1 e 2), base 100, peso 1 e prompts base."""
    p = ProfileConfig.objects.create(
        name="Perfil Padrão",
        is_active=True,
        model_name="deepseek-v4-flash",
        default_max_iterations=3,
        default_max_budget_usd=2.50,
        default_max_time_seconds=300,
    )
    # IDs forçados a 1 e 2 para casar com os mocks (valid_axis_ids=[1, 2]).
    QualityAxis.objects.create(pk=1, profile=p, name="Clareza", weight=1.0, base_score=100.0,
                               deduction_rules="Deduza por ambiguidade ou falta de coesão.")
    QualityAxis.objects.create(pk=2, profile=p, name="Rigor", weight=1.0, base_score=100.0,
                               deduction_rules="Deduza por erro factual ou gramatical.")
    SystemPrompt.objects.create(profile=p, role_type=PromptRole.WRITER,
                                content="Você é um redator profissional e conciso.")
    SystemPrompt.objects.create(profile=p, role_type=PromptRole.GUARDRAIL,
                                content="Audite fidelidade ao tema e ausência de alucinação.")
    SystemPrompt.objects.create(profile=p, role_type=PromptRole.AUDITOR,
                                content="Você é um corretor rigoroso de qualidade textual.")
    return p


@pytest.fixture
def task_execution_factory(db, user, profile):
    """Fábrica de TaskExecution pré-configurada para os testes do pipeline."""

    def _factory(status="PENDING", max_budget_usd="2.50", max_iterations=3, max_time_seconds=300, **kwargs):
        return TaskExecution.objects.create(
            user=user,
            profile=profile,
            original_prompt=kwargs.pop("original_prompt", "Escreva um parágrafo sobre sustentabilidade."),
            status=status,
            max_budget_usd=max_budget_usd,
            max_iterations=max_iterations,
            max_time_seconds=max_time_seconds,
            **kwargs,
        )

    return _factory
