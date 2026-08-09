"""
Catálogo dinâmico de modelos LLM (OpenCode Go).

Os modelos NÃO são hardcoded como TextChoices. A lista é consultada em runtime
no endpoint público https://opencode.ai/zen/go/v1/models, garantindo que novos
modelos sejam selecionáveis sem alteração de código.

Este módulo fornece uma fonte única para o Admin popular as choices de
`ProfileConfig.model_name`. Em ambientes sem rede (testes/dev), retorna um
fallback determinístico sem I/O.
"""
import logging
from typing import Dict, List

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

MODEL_CACHE: List[Dict] = []


def fetch_available_models(force_refresh: bool = False) -> List[Dict]:
    """Retorna a lista de modelos disponíveis no catálogo OpenCode Go.

    Usa um cache em memória simples. Em caso de falha de rede (ex.: ambiente de
    teste ou desenvolvimento offline), degrada graciosamente para o fallback
    determinístico baseado em DEFAULT_MODEL_NAME.
    """
    global MODEL_CACHE
    if MODEL_CACHE and not force_refresh:
        return MODEL_CACHE

    try:
        response = httpx.get(settings.OPENCODE_MODELS_URL, timeout=5.0)
        response.raise_for_status()
        data = response.json()
        MODEL_CACHE = data.get('data', [])
    except (httpx.HTTPError, ValueError) as exc:  # noqa: BLE001
        logger.warning("Falha ao consultar catálogo de modelos: %s. Usando fallback.", exc)
        MODEL_CACHE = [{"id": settings.DEFAULT_MODEL_NAME}]

    return MODEL_CACHE


def get_model_choices() -> List[tuple]:
    """Choices (value, label) prontas para o campo `model_name` no Admin."""
    models = fetch_available_models()
    if not models:
        models = [{"id": settings.DEFAULT_MODEL_NAME}]
    return [(m.get('id', settings.DEFAULT_MODEL_NAME), m.get('id', settings.DEFAULT_MODEL_NAME)) for m in models]
