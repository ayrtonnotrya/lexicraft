"""Agente Guard-rail — audita fidelidade e escopo do texto em relação ao original.

Contrato de saída: `GuardrailResponseSchema`. Decisão booleana `is_approved` que
alimenta a Regra dos 3 Strikes.
"""
import json
from typing import Dict

from apps.orchestrator.schemas import GuardrailResponseSchema
from apps.orchestrator.services.prompt_builder import build_guardrail_prompt

from .client import build_usage_dict, get_async_client


async def call_guardrail_agent(
    system_prompt: str,
    original_prompt: str,
    generated_text: str,
    model: str,
) -> Dict:
    """Chama o Guard-rail e valida a saída com `GuardrailResponseSchema`.

    Retorna um dict com `parsed_payload`, `prompt_tokens`, `completion_tokens`
    e `total_tokens`.
    """
    base_prompt = build_guardrail_prompt(system_prompt)
    # JSON Schema injetado também garante que o prompt contenha "json", requisito
    # do provedor para o modo response_format=json_object.
    schema_json = json.dumps(GuardrailResponseSchema.model_json_schema())
    full_system_prompt = (
        f"{base_prompt}\n\n"
        f"IMPORTANTE: Você deve retornar OBRIGATORIAMENTE um JSON válido seguindo "
        f"exatamente este schema:\n{schema_json}"
    )

    # Fechamento explícito do client evita o RuntimeError('Event loop is closed')
    # ao final de `asyncio.run()`.
    async with get_async_client() as client:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": full_system_prompt},
                {
                    "role": "user",
                    "content": (
                        f"<user_input>\n{original_prompt}\n</user_input>\n\n"
                        f"<generated_text>\n{generated_text}\n</generated_text>"
                    ),
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
        )
        content = response.choices[0].message.content

    parsed = GuardrailResponseSchema.model_validate_json(content)
    usage = build_usage_dict(response.usage)

    return {"parsed_payload": parsed, **usage}