"""Agentes Corretores Paralelos (Tribunal) — auditoria por eixo de qualidade.

Contrato de saída: `AuditorResponseSchema`, gerado dinamicamente via
`build_dynamic_auditor_schema(valid_axis_ids)` para travar o `axis_id` em um
Literal exato e exigir cobertura integral dos eixos.
"""
from typing import Dict, List

from apps.orchestrator.schemas import build_dynamic_auditor_schema
from apps.orchestrator.services.prompt_builder import build_auditor_prompt

from .client import build_usage_dict, get_async_client


async def call_auditor_agent(
    system_prompt: str,
    user_text: str,
    valid_axis_ids: List[int],
    model: str,
    axes: List[Dict] | None = None,
) -> Dict:
    """Chama um Corretor e valida a saída com o schema dinâmico.

    Retorna um dict com `parsed_payload`, `prompt_tokens`, `completion_tokens`
    e `total_tokens`. O `ValidationError` (ex.: axis_id alucinado ou critério
    omitido) propaga para o orquestrador, que o converte em 1 Strike.
    """
    AuditorResponseSchema = build_dynamic_auditor_schema(valid_axis_ids)

    axes = axes or [
        {"id": aid, "name": f"Eixo {aid}", "base_score": 100, "deduction_rules": "Avalie a aderência deste eixo."}
        for aid in valid_axis_ids
    ]

    full_system_prompt = build_auditor_prompt(system_prompt, axes, AuditorResponseSchema)

    # Fechamento explícito do client evita o RuntimeError('Event loop is closed')
    # ao final de `asyncio.run()`.
    async with get_async_client() as client:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": full_system_prompt},
                {"role": "user", "content": f"<user_input>\n{user_text}\n</user_input>"},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,  # Determinismo avaliativo
        )
        content = response.choices[0].message.content

    parsed = AuditorResponseSchema.model_validate_json(content)
    usage = build_usage_dict(response.usage)

    return {"parsed_payload": parsed, **usage}