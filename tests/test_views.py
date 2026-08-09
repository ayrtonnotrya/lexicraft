"""Testes de Views HTMX e Constraints do banco.

Fonte da verdade: docs/TEST_SCENARIOS.md (Sessões 4 e 5).
"""
import pytest
from django.db import IntegrityError
from django.urls import reverse

from apps.core.choices import TaskStatus
from apps.orchestrator.models import TaskExecution
from apps.profiles.models import QualityAxis


# ---------------------------------------------------------------------------
# Cenário K: Polling Dinâmico do Progresso com HTMX
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_htmx_task_status_polling(client, user, task_execution_factory):
    client.force_login(user)
    task = task_execution_factory(status=TaskStatus.RUNNING, current_step='Guard-rail (Tentativa 1/3)')
    url = reverse('dashboard:task_status_partial', args=[task.id])

    # Requisição HTMX -> fragmento parcial, sem layout completo.
    response = client.get(url, HTTP_HX_REQUEST='true')
    assert response.status_code == 200
    assert '<html' not in response.content.decode()
    assert 'Guard-rail (Tentativa 1/3)' in response.content.decode()

    # Acesso direto sem header HTMX -> bloqueado (400 conforme design).
    bad_response = client.get(url)
    assert bad_response.status_code == 400


@pytest.mark.django_db
def test_task_status_partial_nao_expõe_task_de_outro_usuario(client, user, task_execution_factory):
    from django.contrib.auth import get_user_model

    other = get_user_model().objects.create_user(username="other", password="x")
    client.force_login(user)
    task = task_execution_factory(status=TaskStatus.RUNNING)
    task.user = other
    task.save(update_fields=['user'])

    url = reverse('dashboard:task_status_partial', args=[task.id])
    response = client.get(url, HTTP_HX_REQUEST='true')
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Cenário J: Proteção Matemática no Banco de Dados (CheckConstraints)
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_constraint_weight_nao_pode_ser_zero(profile):
    with pytest.raises(IntegrityError):
        QualityAxis.objects.create(
            profile=profile, name="Eixo Inválido", weight=0.0, base_score=100.0, deduction_rules="x"
        )


@pytest.mark.django_db
def test_constraint_weight_nao_pode_ser_negativo(profile):
    with pytest.raises(IntegrityError):
        QualityAxis.objects.create(
            profile=profile, name="Eixo Inválido", weight=-1.5, base_score=100.0, deduction_rules="x"
        )


@pytest.mark.django_db
def test_constraint_base_score_nao_pode_ser_zero(profile):
    with pytest.raises(IntegrityError):
        QualityAxis.objects.create(
            profile=profile, name="Eixo Inválido", weight=1.0, base_score=0.0, deduction_rules="x"
        )


@pytest.mark.django_db
def test_constraint_custo_nao_pode_ser_negativo(user, profile):
    with pytest.raises(IntegrityError):
        TaskExecution.objects.create(
            user=user,
            profile=profile,
            original_prompt="texto",
            status=TaskStatus.RUNNING,
            max_budget_usd="2.50",
            max_time_seconds=300,
            accumulated_cost_usd=-0.50,
        )
