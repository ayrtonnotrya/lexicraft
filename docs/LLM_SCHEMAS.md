# LLM_SCHEMAS.md

## Especificação de Contratos de Entrada e Saída (Structured Outputs) para Agentes LLM

Este documento define a fonte de verdade absoluta para todas as interfaces de comunicação entre o backend em Python (Celery/Orquestrador) e as APIs de Large Language Models no **LexiCraft**. Ele garante que o motor matemático (`math_engine.py`) e as engrenagens de estado recebam dados determinísticos, validados e perfeitamente estruturados.

---

### 1. Filosofia de Contratos Rígidos (Structured Outputs)

Para que o orquestrador autônomo opere em loop fechado sem intervenção humana, a previsibilidade da saída do LLM é inegociável. Modelos de linguagem sofrem de alucinação de formato, injeção de marcadores Markdown indesejados e preenchimentos conversacionais.

Para mitigar 100% desses riscos, o LexiCraft implementa a filosofia de **Structured Outputs**:
1. **Pydantic como Fonte da Verdade:** Todos os retornos esperados da IA são modelados como classes `pydantic.BaseModel`. O Pydantic realiza validação de tipos, *bounds* numéricos (ex: `ge=0.0`) e coerência de chaves.
2. **Compatibilidade Universal (OpenCode Go / OpenAI-Compatible):** Utiliza-se o endpoint padrão com `response_format={"type": "json_object"}` e o schema injetado via prompt, garantindo que qualquer modelo open-source ou proprietário suporte a requisição sem erros de API (`400 Bad Request` por flags restritas como `strict: true`).
3. **Isolamento de Domínio:** A IA não toma decisões de roteamento da aplicação; ela apenas preenche o contrato (JSON). O código Python lê o contrato e executa a lógica de negócio.

---

### 2. Schema do Agente Redator (`WriterResponseSchema`)

**Justificativa:** 
Forçar o LLM a empacotar o texto dentro de uma chave `"generated_text"` impede vazamento de pensamentos e evita a poluição do texto final com blocos de código Markdown (` ``` `).

```python
from pydantic import BaseModel, Field

class WriterResponseSchema(BaseModel):
    """
    Contrato de saída para o Agente Redator.
    Garante a extração limpa do texto gerado, sem ruídos conversacionais.
    """
    generated_text: str = Field(
        ..., 
        description="O texto final gerado ou reescrito, livre de saudações, explicações adicionais ou formatações markdown de bloco de código."
    )
```

---

### 3. Schema do Agente Guard-rail (`GuardrailResponseSchema`)

**Justificativa:** 
O Guard-rail alimenta a **Regra dos 3 Strikes**. Seu schema exige *Chain-of-Thought* (`reasoning`) para forçar o modelo a pensar antes de decidir o booleano de aprovação, maximizando a precisão analítica.

```python
from pydantic import BaseModel, Field
from typing import Optional

class GuardrailResponseSchema(BaseModel):
    """
    Contrato de saída para o Agente Guard-rail (Auditor de Fidelidade e Escopo).
    Decide se o texto avança para o Tribunal ou volta para o Redator (Retentativa).
    """
    reasoning: str = Field(
        ..., 
        description="Análise detalhada (Chain-of-Thought) comparando o texto gerado com o prompt original para justificar alucinação, fuga de tema ou aprovação."
    )
    is_approved: bool = Field(
        ..., 
        description="True se o texto respeita perfeitamente o escopo exigido e não possui alucinações. False caso contrário."
    )
    feedback_for_writer: Optional[str] = Field(
        None, 
        description="Obrigatório se is_approved for False. Instruções exatas e diretas para o Redator consertar o texto na próxima iteração do ciclo."
    )
```

---

### 4. Schema do Agente Corretor / Tribunal (`build_dynamic_auditor_schema`)

**Justificativa:** 
Contrato crítico injetado no `math_engine.py`. Restrições numéricas rigorosas impedem alucinações matemáticas (como deduções negativas). O schema, porém, não pode ser uma classe estática: Large Language Models frequentemente inventam `axis_id` inexistentes no banco ou, por acomodação, omitem critérios válidos, retornando apenas os eixos que julgaram convenientes. Um contrato estático com `axis_id: int` aceitaria qualquer inteiro e excluiria silenciosamente eixos, corrompendo a barganha de Nash ($W(x)$ cairia por ausência de variáveis). Por isso, o schema é gerado dinamicamente a cada execução a partir do conjunto exato de `axis_id` vigentes no `ProfileConfig`, forçando o `axis_id` a um `Literal` exato e exigindo um item por eixo via `@field_validator`.

```python
from pydantic import BaseModel, Field, field_validator, create_model, ValidationError
from typing import List, Type, Literal

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
            description="ID inteiro exato do eixo de qualidade avaliado, obrigatoriamente idêntico a um dos IDs fornecidos nas regras do prompt do sistema."
        )
        criterion_name: str = Field(
            ...,
            description="Nome exato do critério de avaliação (ex: 'Clareza', 'Rigor Gramatical')."
        )
        points_to_deduct: float = Field(
            ...,
            ge=0.0,
            description="Quantidade absoluta de pontos a deduzir. Deve ser 0.0 se não houver nenhuma infração. Nunca deve exceder a nota base do critério."
        )
        reasoning: str = Field(
            ...,
            description="Explicação detalhada da dedução apontando o trecho do texto (citação) onde ocorreu a infração."
        )

    required_ids = set(valid_axis_ids)

    class AuditorResponseSchema(BaseModel):
        """
        Contrato global retornado por um Corretor Paralelo (ou Desempate).
        """
        summary: str = Field(
            ...,
            description="Resumo executivo de 1 a 2 parágrafos da auditoria do texto, focando nos principais acertos e erros encontrados."
        )
        deductions: List[DeductionItem] = Field(
            ...,
            description="Lista de avaliações. DEVE conter rigorosamente UM item para CADA eixo de qualidade solicitado no prompt do sistema, sem omissões."
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
```

---

### 5. Exemplo de Integração (Cliente Assíncrono via SDK / API Compatível)

Integração universal robusta, garantindo o funcionamento em provedores como OpenAI e OpenCode Go sem falhas de payload strict.

```python
import asyncio
import json
from typing import Dict, Any, List
from openai import AsyncOpenAI
from django.conf import settings
from apps.orchestrator.schemas import (
    build_dynamic_auditor_schema, 
    GuardrailResponseSchema, 
    WriterResponseSchema
)

# Inicialização limpa: Utiliza as variáveis de ambiente baseadas no provedor OpenCode Go ou OpenAI.
client = AsyncOpenAI(
    api_key=settings.OPENAI_API_KEY,
    base_url=settings.OPENAI_BASE_URL,
)

async def call_auditor_agent(
    system_prompt: str, 
    user_text: str, 
    valid_axis_ids: List[int],
    model: str = settings.DEFAULT_MODEL_NAME
) -> Dict[str, Any]:
    """
    Chamada assíncrona garantindo compatibilidade com QUALQUER provedor OpenAI-Compatible.
    O schema do corretor é gerado dinamicamente a partir do conjunto exato de
    `axis_id` configurados para a execução corrente.
    """
    # 0. Geração do schema dinâmico: trancar o `axis_id` em um Literal exato
    #    e exigir coincidência integral com o `valid_axis_ids`.
    AuditorResponseSchema = build_dynamic_auditor_schema(valid_axis_ids)

    # 1. Injeção do Schema JSON diretamente no prompt para direcionar a saída do LLM
    schema_json_str = json.dumps(AuditorResponseSchema.model_json_schema())
    full_system_prompt = (
        f"{system_prompt}\n\n"
        f"IMPORTANTE: Você deve retornar OBRIGATORIAMENTE um JSON válido seguindo "
        f"exatamente este schema: {schema_json_str}"
    )

    # 2. Chamada à API utilizando Universal JSON Mode
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": full_system_prompt},
            {"role": "user", "content": f"<user_input>\n{user_text}\n</user_input>"}
        ],
        response_format={"type": "json_object"},
        temperature=0.0, # Determinismo avaliativo
    )
    
    message_content = response.choices[0].message.content
    usage = response.usage
    
    # 3. Validação nativa do Pydantic (Gera ValidationError imediato se houver alucinação de formato, ID inexistente ou critério omitido)
    parsed_payload = AuditorResponseSchema.model_validate_json(message_content)
    
    return {
        "parsed_payload": parsed_payload, 
        "prompt_tokens": usage.prompt_tokens if usage else 0,
        "completion_tokens": usage.completion_tokens if usage else 0,
        "total_tokens": usage.total_tokens if usage else 0,
    }

# Exemplo de chamadas paralelas para o Tribunal (Passo 3 da Arquitetura)
async def execute_parallel_tribunal(
    system_prompt_auditor: str, 
    text_to_evaluate: str,
    valid_axis_ids: List[int]
) -> tuple:
    """
    Executa os corretores simultaneamente, colhendo deduções puras validadas pelo Pydantic.
    """
    task1 = call_auditor_agent(system_prompt_auditor, text_to_evaluate, valid_axis_ids)
    task2 = call_auditor_agent(system_prompt_auditor, text_to_evaluate, valid_axis_ids)
    
    # Resolução assíncrona de I/O em paralelo
    resultado_corretor_1, resultado_corretor_2 = await asyncio.gather(task1, task2)
    
    return resultado_corretor_1, resultado_corretor_2
```
