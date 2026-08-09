"""Testes do Motor Matemático — domínio 100% puro, sem Django DB.

Fonte da verdade: docs/MATH_SPEC.md (Sessão 7) e docs/TEST_SCENARIOS.md (Sessão 2).
"""
import pytest

from apps.orchestrator.services.math_engine import (
    calculate_delta_w,
    calculate_nash_bargaining,
    evaluate_tribunal_divergence,
)


def _criteria(items):
    """Converte listas de tuplas (axis_id, base, weight, deductions) em CriterionConfig."""
    return [
        {"axis_id": aid, "base_score": base, "weight": weight, "deductions": ded}
        for aid, base, weight, ded in items
    ]


# ---------------------------------------------------------------------------
# Cenário 1: Pontuação Perfeita (Base Padrão)
# ---------------------------------------------------------------------------
def test_cenario_1_pontuacao_perfeita():
    criteria = _criteria([(1, 100, 1.0, 0), (2, 100, 1.0, 0), (3, 100, 1.0, 0)])
    result = calculate_nash_bargaining(criteria)

    assert result["normalized_weights"] == {1: 0.333333, 2: 0.333333, 3: 0.333333}
    assert result["normalized_scores"] == {1: 1.0, 2: 1.0, 3: 1.0}
    assert result["raw_scores"] == {1: 100.0, 2: 100.0, 3: 100.0}
    assert result["nash_score"] == 1.000000


# ---------------------------------------------------------------------------
# Cenário 2: Tratamento de Borda e Colapso Catastrófico (S_min)
# ---------------------------------------------------------------------------
def test_cenario_2_colapso_catastrofico_s_min():
    criteria = _criteria([(1, 100, 1.0, 0), (2, 100, 1.0, 150)])
    result = calculate_nash_bargaining(criteria)

    assert result["normalized_weights"] == {1: 0.5, 2: 0.5}
    assert result["raw_scores"][1] == 100.0
    # Dedução 150 > base 100 -> nota bruta travada em 0.0, nunca negativa.
    assert result["raw_scores"][2] == 0.0
    # Piso S_min = 0.01 impede o colapso do produto.
    assert result["normalized_scores"][1] == 1.0
    assert result["normalized_scores"][2] == 0.01
    # sqrt(1.0 * 0.01) == 0.1
    assert result["nash_score"] == pytest.approx(0.100000, abs=1e-6)


# ---------------------------------------------------------------------------
# Cenário 3: Nash Assimétrico vs Média
# ---------------------------------------------------------------------------
def test_cenario_3_nash_assimetrico_penaliza_discrepancia():
    criteria = _criteria([(1, 100, 1.0, 10), (2, 100, 1.0, 80)])
    result = calculate_nash_bargaining(criteria)

    assert result["normalized_scores"] == {1: 0.9, 2: 0.2}
    naive_mean = (0.9 + 0.2) / 2
    assert naive_mean == pytest.approx(0.55)
    # sqrt(0.9 * 0.2) == 0.424264...
    assert result["nash_score"] == pytest.approx(0.424264, abs=1e-6)
    assert result["nash_score"] < naive_mean


# ---------------------------------------------------------------------------
# Cenário 4: Pesos Diferentes e Distribuição
# ---------------------------------------------------------------------------
def test_cenario_4_pesos_diferentes():
    criteria = _criteria([(1, 100, 2.0, 10), (2, 100, 1.0, 20)])
    result = calculate_nash_bargaining(criteria)

    assert result["normalized_weights"] == {1: pytest.approx(0.666667, abs=1e-6),
                                            2: pytest.approx(0.333333, abs=1e-6)}
    assert result["normalized_scores"] == {1: 0.9, 2: 0.8}
    assert result["nash_score"] == pytest.approx(0.865350, abs=1e-6)


# ---------------------------------------------------------------------------
# Cenário 5: Avaliação de Divergência do Tribunal
# ---------------------------------------------------------------------------
def test_cenario_5_divergencia_aciona_desempate():
    deductions_1 = {1: 10.0, 2: 0.0}
    deductions_2 = {1: 25.0, 2: 0.0}
    bases = {1: 100.0, 2: 100.0}

    assert evaluate_tribunal_divergence(deductions_1, deductions_2, bases, threshold=0.10) is True


def test_divergencia_dentro_do_limiar_nao_aciona_desempate():
    deductions_1 = {1: 10.0, 2: 5.0}
    deductions_2 = {1: 12.0, 2: 6.0}
    bases = {1: 100.0, 2: 100.0}
    # |10-12|/100 = 0.02; |5-6|/100 = 0.01 — ambos <= 10%.
    assert evaluate_tribunal_divergence(deductions_1, deductions_2, bases, threshold=0.10) is False


# ---------------------------------------------------------------------------
# Tratamentos de borda do motor
# ---------------------------------------------------------------------------
def test_criteria_vazio_levanta_valueerror():
    with pytest.raises(ValueError):
        calculate_nash_bargaining([])


def test_soma_pesos_zero_levanta_valueerror():
    criteria = _criteria([(1, 100, 0.0, 0), (2, 100, 0.0, 0)])
    with pytest.raises(ValueError):
        calculate_nash_bargaining(criteria)


def test_calculate_delta_w():
    assert calculate_delta_w(0.9, 0.85) == pytest.approx(0.05)
    assert calculate_delta_w(0.74, 0.82) == pytest.approx(-0.08)
    assert calculate_delta_w(0.86, 0.85) == pytest.approx(0.01)
