"""Fábricas de mocks determinísticos (Zero Network) para os agentes LLM.

Fonte da verdade: docs/TEST_SCENARIOS.md (Sessão 4.1).
Todos os retornos são instâncias validadas dos schemas Pydantic reais.
"""
from unittest.mock import AsyncMock

from apps.orchestrator.schemas import (
    GuardrailResponseSchema,
    WriterResponseSchema,
    build_dynamic_auditor_schema,
)


def get_mock_guardrail_approved() -> GuardrailResponseSchema:
    return GuardrailResponseSchema(
        reasoning="O texto cumpriu 100% das regras estipuladas e não possui alucinações.",
        is_approved=True,
        feedback_for_writer=None,
    )


def get_mock_guardrail_rejected() -> GuardrailResponseSchema:
    return GuardrailResponseSchema(
        reasoning="O texto alucinou fatos sobre a tecnologia X.",
        is_approved=False,
        feedback_for_writer="Remova qualquer menção à tecnologia X imediatamente.",
    )


def build_mock_auditor_payload(valid_axis_ids, deductions_by_axis, summary="Texto impecável."):
    """Monta um payload de corretor já validado pelo schema dinâmico."""
    schema = build_dynamic_auditor_schema(valid_axis_ids)
    deductions = [
        {
            "axis_id": aid,
            "criterion_name": f"Eixo {aid}",
            "points_to_deduct": pts,
            "reasoning": "-",
        }
        for aid, pts in deductions_by_axis.items()
    ]
    return schema(summary=summary, deductions=deductions)


def writer_result(generated_text="Texto brilhante.", prompt_tokens=100, completion_tokens=50):
    return {
        "parsed_payload": WriterResponseSchema(generated_text=generated_text),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    }


def guardrail_result(payload, prompt_tokens=80, completion_tokens=10):
    return {
        "parsed_payload": payload,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    }


def auditor_result(payload, prompt_tokens=200, completion_tokens=100):
    return {
        "parsed_payload": payload,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    }


def make_async_mock(*returns):
    """Cria um AsyncMock que devolve, em sequência, os valores fornecidos.

    Se `returns` possuir um único elemento, o mock sempre retorna esse valor;
    caso contrário, itera pelo `side_effect` na ordem dada.
    """
    mock = AsyncMock()
    if len(returns) == 1:
        mock.return_value = returns[0]
    else:
        mock.side_effect = list(returns)
    return mock
