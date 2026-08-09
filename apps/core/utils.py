"""Utilitários compartilhados do LexiCraft (mixins, helpers e funções puras).

Aqui residem ajudantes independentes de domínio, como o cálculo de custo de
tokens, que pode ser reutilizado por tasks e agentes.
"""
from decimal import Decimal

from django.conf import settings


def estimate_cost_usd(
    prompt_tokens: int,
    completion_tokens: int,
    cost_per_1m_prompt: float | None = None,
    cost_per_1m_completion: float | None = None,
) -> Decimal:
    """Estima o custo em USD de uma chamada de LLM usando a tabela estática.

    Equação de Isocusto (docs/MATH_SPEC.md, Sessão 4.2):
        custo = (prompt_tokens / 1e6) * P_prompt + (completion_tokens / 1e6) * P_completion

    Argumentos:
        prompt_tokens: Tokens de entrada (prompt).
        completion_tokens: Tokens de saída (completion).
        cost_per_1m_prompt: USD por 1M de tokens de prompt (fallback via settings).
        cost_per_1m_completion: USD por 1M de tokens de completion (fallback via settings).

    Retorna:
        Decimal com o custo estimado em USD.
    """
    pp = cost_per_1m_prompt if cost_per_1m_prompt is not None else settings.COST_PER_1M_PROMPT_TOKENS
    pc = cost_per_1m_completion if cost_per_1m_completion is not None else settings.COST_PER_1M_COMPLETION_TOKENS

    prompt_cost = (Decimal(prompt_tokens) / Decimal(1_000_000)) * Decimal(str(pp))
    completion_cost = (Decimal(completion_tokens) / Decimal(1_000_000)) * Decimal(str(pc))
    return prompt_cost + completion_cost
