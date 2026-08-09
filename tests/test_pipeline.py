"""Testes de integração do Pipeline Agêntico (Celery) — Zero Network garantido.

Fonte da verdade: docs/TEST_SCENARIOS.md (Sessão 3).
Todos os agentes LLM são mockados (AsyncMock) e retornam instâncias Pydantic.
"""
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from pydantic import ValidationError

from apps.core.choices import AuditorType, TaskStatus
from apps.orchestrator.models import AuditorResult
from apps.orchestrator.schemas import build_dynamic_auditor_schema
from apps.orchestrator.tasks import reap_zombie_tasks, run_optimization_pipeline

from tests.mocks.agents import (
    auditor_result,
    build_mock_auditor_payload,
    guardrail_result,
    get_mock_guardrail_approved,
    writer_result,
)

VALID_AXIS_IDS = [1, 2]

PATCH_WRITER = 'apps.orchestrator.agents.writer.call_writer_agent'
PATCH_GUARDRAIL = 'apps.orchestrator.agents.guardrail.call_guardrail_agent'
PATCH_AUDITOR = 'apps.orchestrator.agents.auditor.call_auditor_agent'


def _approved():
    return guardrail_result(get_mock_guardrail_approved())


def _zero_deductions():
    return auditor_result(build_mock_auditor_payload(VALID_AXIS_IDS, {1: 0.0, 2: 0.0}))


# ---------------------------------------------------------------------------
# Cenário A: Fluxo Perfeito (Golden Path)
# ---------------------------------------------------------------------------
@pytest.mark.django_db(transaction=True)
@patch(PATCH_AUDITOR)
@patch(PATCH_GUARDRAIL)
@patch(PATCH_WRITER)
def test_cenario_a_golden_path(mock_writer, mock_guardrail, mock_auditor, task_execution_factory):
    task = task_execution_factory(max_budget_usd="2.50")
    mock_writer.return_value = writer_result()
    mock_guardrail.return_value = _approved()
    mock_auditor.return_value = _zero_deductions()

    run_optimization_pipeline(task.id)

    task.refresh_from_db()
    assert task.status == TaskStatus.COMPLETED
    assert task.snapshots.count() == 1
    assert task.final_score >= 0.95
    assert task.final_text is not None


# ---------------------------------------------------------------------------
# Cenário B: Resiliência do Guard-rail (3 Strikes com Reset)
# ---------------------------------------------------------------------------
@pytest.mark.django_db(transaction=True)
@patch(PATCH_AUDITOR)
@patch(PATCH_GUARDRAIL)
@patch(PATCH_WRITER)
def test_cenario_b_strikes_com_reset(mock_writer, mock_guardrail, mock_auditor, task_execution_factory):
    task = task_execution_factory()
    mock_writer.return_value = writer_result()
    mock_guardrail.side_effect = [
        guardrail_result(get_mock_guardrail_rejected()),
        guardrail_result(get_mock_guardrail_rejected()),
        _approved(),
    ]
    mock_auditor.return_value = _zero_deductions()

    run_optimization_pipeline(task.id)

    task.refresh_from_db()
    assert task.status != TaskStatus.ABORTED_GUARDRAIL_STRIKES
    assert task.snapshots.count() == 1
    # Redator foi reacionado nas 3 tentativas antes da aprovação.
    assert mock_writer.await_count == 3


# ---------------------------------------------------------------------------
# Cenário C: Aborto Irrecuperável por Falha Crítica de Escopo
# ---------------------------------------------------------------------------
@pytest.mark.django_db(transaction=True)
@patch(PATCH_AUDITOR)
@patch(PATCH_GUARDRAIL)
@patch(PATCH_WRITER)
def test_cenario_c_abort_3_strikes_escopo(mock_writer, mock_guardrail, mock_auditor, task_execution_factory):
    task = task_execution_factory()
    mock_writer.return_value = writer_result()
    rejected = guardrail_result(get_mock_guardrail_rejected())
    mock_guardrail.side_effect = [rejected, rejected, rejected]

    run_optimization_pipeline(task.id)

    task.refresh_from_db()
    assert task.status == TaskStatus.ABORTED_GUARDRAIL_STRIKES
    assert task.snapshots.count() == 0
    assert mock_writer.await_count == 3


# ---------------------------------------------------------------------------
# Cenário D: Instanciação do 3º Corretor no Tribunal
# ---------------------------------------------------------------------------
@pytest.mark.django_db(transaction=True)
@patch(PATCH_AUDITOR)
@patch(PATCH_GUARDRAIL)
@patch(PATCH_WRITER)
def test_cenario_d_terceiro_corretor(mock_writer, mock_guardrail, mock_auditor, task_execution_factory):
    task = task_execution_factory(max_iterations=1)
    mock_writer.return_value = writer_result()
    mock_guardrail.return_value = _approved()

    aud1 = auditor_result(build_mock_auditor_payload(VALID_AXIS_IDS, {1: 10.0, 2: 0.0}))
    aud2 = auditor_result(build_mock_auditor_payload(VALID_AXIS_IDS, {1: 40.0, 2: 0.0}))
    aud3 = auditor_result(build_mock_auditor_payload(VALID_AXIS_IDS, {1: 25.0, 2: 0.0}))
    # Ordem: corretor1, corretor2 (via gather) e, por divergência > 10%, o desempate.
    mock_auditor.side_effect = [aud1, aud2, aud3]

    run_optimization_pipeline(task.id)

    task.refresh_from_db()
    snapshot = task.snapshots.first()
    assert task.snapshots.count() == 1
    # Rigorosamente três AuditorResult (um para cada corretor).
    assert snapshot.auditor_results.count() == 3
    types = set(snapshot.auditor_results.values_list('auditor_type', flat=True))
    assert types == {AuditorType.CORRETOR_1, AuditorType.CORRETOR_2, AuditorType.DESEMPATE}
    # Média estrita (10+40+25)/3 = 25 -> S1 = 75/100 = 0.75.
    assert snapshot.normalized_scores['1'] == pytest.approx(0.75, abs=1e-6)


# ---------------------------------------------------------------------------
# Cenário E: Rollback por Teto Orçamentário (C_max)
# ---------------------------------------------------------------------------
@pytest.mark.django_db(transaction=True)
@patch(PATCH_AUDITOR)
@patch(PATCH_GUARDRAIL)
@patch(PATCH_WRITER)
def test_cenario_e_rollback_orcamento(mock_writer, mock_guardrail, mock_auditor, task_execution_factory):
    task = task_execution_factory(max_budget_usd="2.50", max_iterations=3)
    # Ciclo 1: tokens modestos. Ciclo 2: 20M tokens de prompt (~US$ 3.00).
    mock_writer.side_effect = [
        writer_result(generated_text="versão 1", prompt_tokens=100, completion_tokens=50),
        writer_result(generated_text="versão 2", prompt_tokens=20_000_000, completion_tokens=50),
    ]
    mock_guardrail.return_value = _approved()
    # Dedução 20 em ambos os eixos -> W = 0.80 (ciclos 1 e 2).
    ded20 = auditor_result(build_mock_auditor_payload(VALID_AXIS_IDS, {1: 20.0, 2: 20.0}))
    mock_auditor.return_value = ded20

    run_optimization_pipeline(task.id)

    task.refresh_from_db()
    assert task.status == TaskStatus.COMPLETED_WITH_ROLLBACK
    assert task.final_score == pytest.approx(0.80, abs=1e-6)
    # O orçamento foi de fato estourado.
    assert float(task.accumulated_cost_usd) >= float(task.max_budget_usd)


# ---------------------------------------------------------------------------
# Cenário F: Rollback por Estagnação de Epsilon (Delta W < Epsilon)
# ---------------------------------------------------------------------------
@pytest.mark.django_db(transaction=True)
@patch(PATCH_AUDITOR)
@patch(PATCH_GUARDRAIL)
@patch(PATCH_WRITER)
def test_cenario_f_estagnacao_epsilon(mock_writer, mock_guardrail, mock_auditor, task_execution_factory):
    task = task_execution_factory(max_iterations=3)
    mock_writer.return_value = writer_result()
    mock_guardrail.return_value = _approved()
    # Ciclo 1: W=0.85 (ded 15). Ciclo 2: W=0.86 (ded 14). Delta = 0.01 < 0.02.
    aud85 = auditor_result(build_mock_auditor_payload(VALID_AXIS_IDS, {1: 15.0, 2: 15.0}))
    aud86 = auditor_result(build_mock_auditor_payload(VALID_AXIS_IDS, {1: 14.0, 2: 14.0}))
    mock_auditor.side_effect = [aud85, aud85, aud86, aud86]

    run_optimization_pipeline(task.id)

    task.refresh_from_db()
    assert task.status == TaskStatus.COMPLETED_WITH_ROLLBACK
    # Melhor versão registrada é a do Ciclo 2 (0.86).
    assert task.final_score == pytest.approx(0.86, abs=1e-6)


# ---------------------------------------------------------------------------
# Cenário G: Degradação Súbita (Delta W < 0) com Rollback Imediato
# ---------------------------------------------------------------------------
@pytest.mark.django_db(transaction=True)
@patch(PATCH_AUDITOR)
@patch(PATCH_GUARDRAIL)
@patch(PATCH_WRITER)
def test_cenario_g_degradacao_sumaria(mock_writer, mock_guardrail, mock_auditor, task_execution_factory):
    task = task_execution_factory(max_iterations=3)
    mock_writer.side_effect = [writer_result(generated_text="versão 1"), writer_result(generated_text="versão 2")]
    mock_guardrail.return_value = _approved()
    # Ciclo 1: W=0.82 (ded 18). Ciclo 2: W=0.74 (ded 26). Delta = -0.08.
    aud82 = auditor_result(build_mock_auditor_payload(VALID_AXIS_IDS, {1: 18.0, 2: 18.0}))
    aud74 = auditor_result(build_mock_auditor_payload(VALID_AXIS_IDS, {1: 26.0, 2: 26.0}))
    mock_auditor.side_effect = [aud82, aud82, aud74, aud74]

    run_optimization_pipeline(task.id)

    task.refresh_from_db()
    assert task.status == TaskStatus.COMPLETED_WITH_ROLLBACK
    # Sem Ciclo 3: exatamente 2 snapshots foram gravados.
    assert task.snapshots.count() == 2
    # Rollback para a melhor versão (Ciclo 1, W=0.82).
    assert task.final_score == pytest.approx(0.82, abs=1e-6)
    assert task.final_text == "versão 1"


# ---------------------------------------------------------------------------
# Cenário H: Schema Dinâmico Rejeita axis_id Alucinado (consome 1 Strike)
# ---------------------------------------------------------------------------
def test_cenario_h_schema_rejeita_axis_id_alucinado():
    schema = build_dynamic_auditor_schema(VALID_AXIS_IDS)
    with pytest.raises(ValidationError):
        schema.model_validate_json(
            '{"summary": "x", "deductions": [{"axis_id": 999, "criterion_name": "C", '
            '"points_to_deduct": 10, "reasoning": "r"}]}'
        )
    # Omissão de um eixo (só o eixo 1) também deve falhar.
    with pytest.raises(ValidationError):
        schema.model_validate_json(
            '{"summary": "x", "deductions": [{"axis_id": 1, "criterion_name": "C", '
            '"points_to_deduct": 10, "reasoning": "r"}]}'
        )


@pytest.mark.django_db(transaction=True)
@patch(PATCH_AUDITOR)
@patch(PATCH_GUARDRAIL)
@patch(PATCH_WRITER)
def test_cenario_h_erro_de_schema_consome_strike(mock_writer, mock_guardrail, mock_auditor, task_execution_factory):
    task = task_execution_factory()
    mock_writer.return_value = writer_result()
    mock_guardrail.return_value = _approved()
    # Auditor sempre levanta ValidationError (schema alucinado/omitido).
    schema = build_dynamic_auditor_schema(VALID_AXIS_IDS)
    try:
        schema.model_validate_json(
            '{"summary": "x", "deductions": [{"axis_id": 999, "criterion_name": "C", '
            '"points_to_deduct": 10, "reasoning": "r"}]}'
        )
    except ValidationError as exc:
        auditor_error = exc
    mock_auditor.side_effect = auditor_error

    run_optimization_pipeline(task.id)

    task.refresh_from_db()
    assert task.status == TaskStatus.ABORTED_GUARDRAIL_STRIKES
    assert task.snapshots.count() == 0
    assert AuditorResult.objects.count() == 0
    assert "Erro de Schema" in (task.current_step or "")


# ---------------------------------------------------------------------------
# Cenário I: Falha de Rede (httpx.TimeoutException) Consome Strike
# ---------------------------------------------------------------------------
@pytest.mark.django_db(transaction=True)
@patch(PATCH_AUDITOR)
@patch(PATCH_GUARDRAIL)
@patch(PATCH_WRITER)
def test_cenario_i_timeout_consome_strike_e_aborta(mock_writer, mock_guardrail, mock_auditor, task_execution_factory):
    task = task_execution_factory()
    mock_writer.return_value = writer_result()
    # Guard-rail sempre levanta TimeoutException -> 3 strikes de infraestrutura.
    mock_guardrail.side_effect = httpx.TimeoutException("timeout de rede")

    # Não deve propagar exceção ao chamador (Worker permanece vivo).
    run_optimization_pipeline(task.id)

    task.refresh_from_db()
    assert task.status == TaskStatus.ABORTED_GUARDRAIL_STRIKES
    assert "infraestrutura" in (task.current_step or "")
    # Heartbeat foi mantido vivo durante a captura.
    assert task.last_heartbeat_at is not None


# ---------------------------------------------------------------------------
# Ceifador de Tarefas Zumbis (reap_zombie_tasks)
# ---------------------------------------------------------------------------
@pytest.mark.django_db(transaction=True)
def test_reap_zombie_tasks(task_execution_factory):
    from django.utils import timezone

    from apps.orchestrator.models import ExecutionSnapshot

    task = task_execution_factory(status=TaskStatus.RUNNING)
    ExecutionSnapshot.objects.create(
        task_execution=task,
        iteration_number=1,
        generated_text="melhor versão",
        nash_score=0.90,
        normalized_scores={},
    )
    # Heartbeat desatualizado há mais de 1 minuto.
    task.last_heartbeat_at = timezone.now() - timedelta(minutes=5)
    task.save(update_fields=['last_heartbeat_at'])

    # Task viva (heartbeat recente) não deve ser coletada.
    alive = task_execution_factory(status=TaskStatus.RUNNING)

    count = reap_zombie_tasks()

    assert count == 1
    task.refresh_from_db()
    assert task.status == TaskStatus.FAILED_TIMEOUT
    assert task.final_score == 0.90
    assert task.final_text == "melhor versão"

    alive.refresh_from_db()
    assert alive.status == TaskStatus.RUNNING


# ---------------------------------------------------------------------------
# Rastreamento de tokens e custo acumulado
# ---------------------------------------------------------------------------
@pytest.mark.django_db(transaction=True)
@patch(PATCH_AUDITOR)
@patch(PATCH_GUARDRAIL)
@patch(PATCH_WRITER)
def test_rastreamento_tokens_e_custo(mock_writer, mock_guardrail, mock_auditor, task_execution_factory):
    task = task_execution_factory()
    mock_writer.return_value = writer_result(prompt_tokens=100, completion_tokens=50)
    mock_guardrail.return_value = _approved()
    mock_auditor.return_value = _zero_deductions()

    run_optimization_pipeline(task.id)

    task.refresh_from_db()
    # Writer (100/50) + Guard-rail (80/10) + 2 Corretores (200/100 cada).
    assert task.accumulated_prompt_tokens == 100 + 80 + 200 + 200
    assert task.accumulated_completion_tokens == 50 + 10 + 100 + 100
    assert float(task.accumulated_cost_usd) > 0


# Helper reutilizado no Cenário B.
def get_mock_guardrail_rejected():
    from tests.mocks.agents import get_mock_guardrail_rejected as _rej
    return _rej()
