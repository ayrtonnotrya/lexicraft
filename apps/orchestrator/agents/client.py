"""
Cliente LLM compartilhado (OpenCode Go / OpenAI-Compatible).

Fornece o cliente `AsyncOpenAI` configurado a partir das settings e um helper
de parsing que extrai o conteúdo e o uso de tokens de uma resposta, aplicando
validação manual via Pydantic (`model_validate_json`) — nunca `.parse()`.
"""
from typing import Any, Dict

from django.conf import settings
from openai import AsyncOpenAI


def get_async_client() -> AsyncOpenAI:
    """Inicializa o cliente assíncrono a partir das variáveis de ambiente."""
    return AsyncOpenAI(
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL,
    )


def build_usage_dict(usage: Any) -> Dict[str, int]:
    """Normaliza a estrutura de uso de tokens para um dict com chaves fixas."""
    if usage is None:
        return {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
    return {
        "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
        "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
        "total_tokens": getattr(usage, "total_tokens", 0) or 0,
    }
