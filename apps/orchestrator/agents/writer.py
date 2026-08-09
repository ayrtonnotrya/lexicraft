"""Agente Redator — gera ou reescreve o texto a partir do prompt e do histórico.

Contrato de saída: `WriterResponseSchema`. Usa Universal JSON Mode
(`response_format={"type": "json_object"}`) com validação manual via Pydantic.
"""
import json
from typing import Dict, Optional

from apps.orchestrator.schemas import WriterResponseSchema
from apps.orchestrator.services.prompt_builder import build_writer_prompt

from .client import build_usage_dict, get_async_client


async def call_writer_agent(
    system_prompt: str,
    original_prompt: str,
    model: str,
    previous_text: Optional[str] = None,
    violations_report: Optional[str] = None,
) -> Dict:
    """Chama o Redator e valida a saída com `WriterResponseSchema`.

    Retorna um dict com `parsed_payload`, `prompt_tokens`, `completion_tokens`
    e `total_tokens`, pronto para alimentar o contador de Isocusto.
    """
    base_prompt = build_writer_prompt(
        system_content=system_prompt,
        original_prompt=original_prompt,
        previous_text=previous_text,
        violations_report=violations_report,
    )
    # O provedor exige que o prompt mencione "json" quando o response_format é
    # json_object; aproveitamos para injetar o schema do contrato e garantir
    # a estrutura esperada na validação Pydantic.
    schema_json = json.dumps(WriterResponseSchema.model_json_schema())
    full_system_prompt = (
        f"{base_prompt}\n\n"
        f"IMPORTANTE: Você deve retornar OBRIGATORIAMENTE um JSON válido seguindo "
        f"exatamente este schema, sem markdown e sem textos extras:\n{schema_json}"
    )

    # Bloco `async with` garante o fechamento explícito do AsyncOpenAI (e do
    # httpx.AsyncClient subjacente) antes que o event loop seja encerrado por
    # `asyncio.run()`, eliminando o RuntimeError('Event loop is closed').
    async with get_async_client() as client:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": full_system_prompt},
                {"role": "user", "content": f"<user_input>\n{original_prompt}\n</user_input>"},
            ],
            response_format={"type": "json_object"},
            temperature=0.7,
        )
        content = response.choices[0].message.content

    parsed = WriterResponseSchema.model_validate_json(content)
    usage = build_usage_dict(response.usage)

    return {"parsed_payload": parsed, **usage}