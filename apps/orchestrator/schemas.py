"""
Contratos de Entrada/Saída (Structured Outputs) dos Agentes LLM do LexiCraft.

Fonte da verdade: docs/LLM_SCHEMAS.md.

Filosofia de compatibilidade (OpenCode Go / OpenAI-Compatible):
    * NUNCA usar `.parse()`, Function Calling atrelado a schema ou `strict: true`.
    * Sempre usar o **Universal JSON Mode** (`response_format={"type": "json_object"}`)
      com o JSON Schema injetado no prompt do sistema.
    * Validar manualmente a string de resposta com `Schema.model_validate_json(...)`.
"""
from pydantic import BaseModel, Field, field_validator
from typing import List, Literal, Optional, Type


class WriterResponseSchema(BaseModel):
    """
    Contrato de saída para o Agente Redator.
    Garante a extração limpa do texto gerado, sem ruídos conversacionais.
    """

    generated_text: str = Field(
        ...,
        description=(
            "O texto final gerado ou reescrito, livre de saudações, explicações "
            "adicionais ou formatações markdown de bloco de código."
        ),
    )


class GuardrailResponseSchema(BaseModel):
    """
    Contrato de saída para o Agente Guard-rail (Auditor de Fidelidade e Escopo).
    Decide se o texto avança para o Tribunal ou volta para o Redator (Retentativa).
    """

    reasoning: str = Field(
        ...,
        description=(
            "Análise detalhada (Chain-of-Thought) comparando o texto gerado com o "
            "prompt original para justificar alucinação, fuga de tema ou aprovação."
        ),
    )
    is_approved: bool = Field(
        ...,
        description="True se o texto respeita perfeitamente o escopo exigido e não possui alucinações. False caso contrário.",
    )
    feedback_for_writer: Optional[str] = Field(
        None,
        description="Obrigatório se is_approved for False. Instruções exatas e diretas para o Redator consertar o texto na próxima iteração do ciclo.",
    )


def build_dynamic_auditor_schema(valid_axis_ids: List[int]) -> Type[BaseModel]:
    """
    Fábrica de schemas Pydantic dinâmicos para o Tribunal de Corretores.

    Recebe o conjunto exato e autoritativo de `axis_id` configurados para o
    Perfil em execução e devolve uma classe `BaseModel` que:

      1. Restringe `axis_id` ao `Literal` exatamente igual a um dos IDs
         fornecidos, recusando qualquer inteiro alucinado pelo LLM.
      2. Valida via `@field_validator('deductions')` que o set de IDs
         retornados é idêntico ao `valid_axis_ids`, abortando o parse se
         algum critério foi omitido por preguiça do modelo.

    O `ValidationError` resultante consome 1 Strike no Guard-rail e interrompe
    o ciclo antes que dados corrompidos cheguem ao `math_engine.py`.
    """
    if not valid_axis_ids:
        raise ValueError("O conjunto de axis_id válidos não pode ser vazio.")

    AxisIdLiteral = Literal[tuple(valid_axis_ids)]  # type: ignore[valid-type]

    class DeductionItem(BaseModel):
        """
        Contrato individual de penalização de um Eixo de Qualidade.
        """

        axis_id: AxisIdLiteral = Field(
            ...,
            description=(
                "ID inteiro exato do eixo de qualidade avaliado, obrigatoriamente "
                "idêntico a um dos IDs fornecidos nas regras do prompt do sistema."
            ),
        )
        criterion_name: str = Field(
            ...,
            description="Nome exato do critério de avaliação (ex: 'Clareza', 'Rigor Gramatical').",
        )
        points_to_deduct: float = Field(
            ...,
            ge=0.0,
            description=(
                "Quantidade absoluta de pontos a deduzir. Deve ser 0.0 se não houver "
                "nenhuma infração. Nunca deve exceder a nota base do critério."
            ),
        )
        reasoning: str = Field(
            ...,
            description=(
                "Explicação detalhada da dedução apontando o trecho do texto "
                "(citação) onde ocorreu a infração."
            ),
        )

    required_ids = set(valid_axis_ids)

    class AuditorResponseSchema(BaseModel):
        """
        Contrato global retornado por um Corretor Paralelo (ou Desempate).
        """

        summary: str = Field(
            ...,
            description="Resumo executivo de 1 a 2 parágrafos da auditoria do texto, focando nos principais acertos e erros encontrados.",
        )
        deductions: List[DeductionItem] = Field(
            ...,
            description="Lista de avaliações. DEVE conter rigorosamente UM item para CADA eixo de qualidade solicitado no prompt do sistema, sem omissões.",
        )

        @field_validator('deductions')
        @classmethod
        def _validate_completeness(cls, deductions: List[DeductionItem]) -> List[DeductionItem]:
            returned_ids = {item.axis_id for item in deductions}
            if returned_ids != required_ids:
                missing = required_ids - returned_ids
                unexpected = returned_ids - required_ids
                raise ValueError(
                    "O conjunto de axis_id retornados não coincide com o esperado. "
                    f"Ausentes/omitidos: {sorted(missing) or 'nenhum'}; "
                    f" inexistentes/alucinados: {sorted(unexpected) or 'nenhum'}."
                )
            return deductions

    return AuditorResponseSchema
