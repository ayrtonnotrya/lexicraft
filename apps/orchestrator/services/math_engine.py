"""
Motor Matemático Determinístico do LexiCraft.

Domínio 100% isolado de I/O e de LLMs: a IA apenas aponta deduções brutas; toda
a agregação, normalização e cálculo geométrico é feito aqui em Python puro.

Fonte da verdade: docs/MATH_SPEC.md e docs/AGENTS.md (Sessão 4.C).

Equações:
    w_i = weight_i / sum(weights)
    Bruta_i = max(0.0, base_i - deductions_i)
    S_i     = max(s_min, min(1.0, Bruta_i / base_i))
    W(x)    = prod(S_i ** w_i)

Borda de segurança: s_min = 0.01 impede o colapso do produto de Nash por zero
(Elemento Absorvente), preservando a comparabilidade marginal entre ciclos.
"""
import math
from typing import Any, Dict, List, TypedDict


class CriterionConfig(TypedDict):
    axis_id: int
    base_score: float
    weight: float
    deductions: float  # Dedução já consolidada pela média do tribunal


def calculate_nash_bargaining(
    criteria: List[CriterionConfig],
    s_min: float = 0.01,
) -> Dict[str, Any]:
    """
    Calcula a Normalização Rígida [0.01, 1.0] e a Barganha de Nash Assimétrica W(x).

    Regras:
    1. Pesos são normalizados: w_i = weight_i / sum(weights).
    2. Nota_Bruta_i = max(0.0, Base_i - Sum_Deductions_i).
    3. S_i = max(s_min, min(1.0, Nota_Bruta_i / Base_i)).
    4. W(x) = Product(S_i ^ w_i).
    """
    if not criteria:
        raise ValueError("A lista de critérios não pode estar vazia.")

    total_weight = sum(c['weight'] for c in criteria)
    if total_weight <= 0:
        raise ValueError("A soma dos pesos deve ser maior que zero.")

    normalized_scores: Dict[int, float] = {}
    raw_scores: Dict[int, float] = {}
    normalized_weights: Dict[int, float] = {}

    nash_product = 1.0

    for item in criteria:
        axis_id = item['axis_id']

        # 1. Normalização do peso (wi)
        w_i = item['weight'] / total_weight
        normalized_weights[axis_id] = w_i

        # 2. Cálculo da Nota Bruta (limitada inferiormente a 0.0)
        raw_score = max(0.0, item['base_score'] - item['deductions'])
        raw_scores[axis_id] = raw_score

        # 3. Normalização Rígida Si no intervalo [s_min, 1.0]
        s_i = max(s_min, min(1.0, raw_score / item['base_score']))
        normalized_scores[axis_id] = s_i

        # 4. Acumulação Geométrica da Barganha de Nash
        nash_product *= math.pow(s_i, w_i)

    return {
        "nash_score": round(nash_product, 6),
        "normalized_scores": {k: round(v, 6) for k, v in normalized_scores.items()},
        "raw_scores": raw_scores,
        "normalized_weights": {k: round(v, 6) for k, v in normalized_weights.items()},
    }


def evaluate_tribunal_divergence(
    deductions_auditor_1: Dict[int, float],
    deductions_auditor_2: Dict[int, float],
    bases: Dict[int, float],
    threshold: float = 0.10,
) -> bool:
    """
    Avalia se existe divergência > threshold (10%) entre dois corretores em
    qualquer eixo avaliado. Retorna True se exigir um 3º Corretor.

    Divergência_i = |D1_i - D2_i| / Base_i
    """
    for axis_id, base_score in bases.items():
        if base_score <= 0:
            continue

        d1 = deductions_auditor_1.get(axis_id, 0.0)
        d2 = deductions_auditor_2.get(axis_id, 0.0)

        divergence = abs(d1 - d2) / base_score
        if divergence > threshold:
            return True

    return False


def calculate_delta_w(w_current: float, w_previous: float) -> float:
    """Calcula o ganho marginal (Delta W) da iteração corrente."""
    return round(w_current - w_previous, 6)
