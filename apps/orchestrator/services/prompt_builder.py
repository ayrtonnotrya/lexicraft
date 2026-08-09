"""
Construção dinâmica de prompts para os agentes LLM do LexiCraft.

Prompts base vivem no banco (SystemPrompt); aqui apenas concatenamos regras de
eixos, peso e o JSON Schema do contrato Pydantic, isolando a semântica do
cálculo matemático (que nunca vai para o prompt).
"""
import json
from typing import Dict, List


def build_writer_prompt(
    system_content: str,
    original_prompt: str,
    previous_text: str | None = None,
    violations_report: str | None = None,
) -> str:
    """Monta o prompt de sistema do Agente Redator, incluindo histórico opcional."""
    parts = [system_content]
    if previous_text:
        parts.append(f"<previous_version>\n{previous_text}\n</previous_version>")
    if violations_report:
        parts.append(f"<infractions>\n{violations_report}\n</infractions>")
    return "\n\n".join(p for p in parts if p)


def build_guardrail_prompt(system_content: str) -> str:
    """Prompt de sistema do Guard-rail (a diretriz base já define fidelidade/escopo)."""
    return system_content


def build_auditor_prompt(
    system_content: str,
    axes: List[Dict],
    schema_model,
) -> str:
    """Prompt de sistema do Corretor com o JSON Schema injetado e regras por eixo.

    Argumentos:
        system_content: Diretriz base do Corretor (SystemPrompt role_type=AUDITOR).
        axes: Lista de dicts com 'id', 'name', 'base_score' e 'deduction_rules'.
        schema_model: A classe Pydantic (AuditorResponseSchema) gerada dinamicamente.
    """
    schema_json_str = json.dumps(schema_model.model_json_schema())
    axes_block = "\n".join(
        f"- Eixo {ax['id']} ({ax['name']}, base={ax['base_score']}): {ax['deduction_rules']}"
        for ax in axes
    )
    return (
        f"{system_content}\n\n"
        f"REGRA DE AVALIAÇÃO (eixos válidos):\n{axes_block}\n\n"
        f"IMPORTANTE: Você deve retornar OBRIGATORIAMENTE um JSON válido seguindo "
        f"exatamente este schema, cobrindo TODOS os eixos listados, sem omitir "
        f"nenhum e sem inventar IDs inexistentes:\n{schema_json_str}"
    )
