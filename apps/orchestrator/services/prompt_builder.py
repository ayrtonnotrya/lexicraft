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
    """Monta o prompt de sistema do Agente Redator, incluindo histórico opcional.

    Um bloco universal de FIDELIDADE é sempre anexado, independente do perfil,
    para combater a tendência do LLM de inventar dados e alterar o registro
    (pedido->decisão, incerteza->certeza) em todas as gerações.
    """
    parts = [system_content]
    if previous_text:
        parts.append(f"<previous_version>\n{previous_text}\n</previous_version>")
    if violations_report:
        parts.append(f"<infractions>\n{violations_report}\n</infractions>")
    parts.append(
        "=== FIDELIDADE ABSOLUTA AO ORIGINAL (OBRIGATÓRIO, EM TODAS AS GERAÇÕES) ===\n"
        "O <user_input> é a FONTE ÚNICA da verdade. Ao reescrever ou otimizar o texto:\n"
        "1. NUNCA invente fatos, dados, números, nomes, prazos, horários, "
        "valores, códigos ou decisões que não constem literalmente no original.\n"
        "2. Preserve o REGISTRO do original: se ele é um pedido/consulta, "
        "continue sendo um pedido/consulta; não o converta em decisão tomada "
        "nem em instrução. Ex.: não troque 'peço que possamos rodar' por "
        "'vamos rodar' nem 'precisamos rodar'.\n"
        "3. Preserve INCERTEZAS e vagueza do original ('provavelmente', "
        "'à tarde', 'ainda preciso analisar', 'em algum momento') — NÃO as "
        "torne definitivas: não adicione 'hoje', datas, horas ou certezas "
        "que não existam no original.\n"
        "4. Não altere o significado nem a intenção de quem fala; apenas "
        "melhore clareza, estrutura, concisão e fluência.\n"
        "5. Em caso de dúvida, mantenha-se o mais próximo possível da "
        "formulação original — nunca preencha lacunas com suposições."
    )
    return "\n\n".join(p for p in parts if p)


def build_guardrail_prompt(system_content: str) -> str:
    """Prompt de sistema do Guard-rail com contrato de saída explícito.

    A diretriz base (do banco) define fidelidade/escopo; aqui reforçamos o
    contrato JSON para o modelo não ecoar o schema nem responder em prosa,
    o que geraria ValidationError e consumiria 1 Strike à toa.
    """
    return (
        f"{system_content}\n\n"
        f"=== FORMATO DE SAÍDA (OBRIGATÓRIO) ===\n"
        f"Responda com UM ÚNICO objeto JSON válido — NUNCA repita o schema, "
        f"nunca use markdown, nunca acrescente texto fora do JSON. O objeto "
        f"deve conter EXATAMENTE estes três campos:\n"
        f"  1. \"reasoning\": string — sua análise comparando o texto gerado "
        f"com o prompt original (fidelidade de fatos, prazos, valores, nomes "
        f"e escopo).\n"
        f"  2. \"is_approved\": booleano — true APENAS se o texto é fiel, "
        f"factual e escopado ao original; false se houver QUALQUER alucinação, "
        f"invenção de dados, prazo/valor/numero novo ou fuga de escopo.\n"
        f"  3. \"feedback_for_writer\": string — OBRIGATÓRIO quando "
        f"is_approved for false; diga exatamente o que corrigir e cite os "
        f"trechos inventados. Pode ser null apenas quando aprovado.\n"
        f"Exemplo da forma do JSON (valores ilustrativos):\n"
        + '{"reasoning": "...", "is_approved": false, '
          '"feedback_for_writer": "Remova o prazo às 12h inventado..."}'
    )


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
    # Rubrica de magnitude: ancora a severidade à percentagem da nota base,
    # impedindo que o LLM trate "pontos" como se a escala fosse 0-10.
    return (
        f"{system_content}\n\n"
        f"REGRA DE AVALIAÇÃO (eixos válidos):\n{axes_block}\n\n"
        f"=== ESCALA DE PONTOS (LEIA ANTES DE DEDUZIR) ===\n"
        f"A pontuação NÃO é 0-10 nem 0-1. Cada eixo tem uma NOTA BASE (na linha "
        f"'base=...' acima). Você deduz uma QUANTIDADE ABSOLUTA de pontos dessa base, "
        f"conforme a gravidade. Use sempre PERCENTUAL DA BASE, nunca intui 5/10:\n"
        f"  • IMPERDOÁVEL (baixa/correção só refazendo): deduza 50%-100% da base\n"
        f"  • GRAVE (prejudica claramente o objetivo do eixo): deduza 25%-50% da base\n"
        f"  • MODERADO (vício notável, merece lapidação): deduza 10%-25% da base\n"
        f"  • LEVE (atenuar mas não ignora): deduza 5%-10% da base\n"
        f"  • NENHUM (sem desvio após dupla varredura): deduza 0% (exija justificativa)\n"
        f"Exemplos concretos: base 100 + erro grave => deduzir 25 a 50 pontos; "
        f"base 50 + erro moderado => deduzir 5 a 12 pontos. SOMA por eixo: se um eixo "
        f"acumula várias infrações, SOME as percentagens — dois erros moderados não "
        f"viram um leve, viram grave (20%+).\n\n"
        f"=== CALIBRAÇÃO OBRIGATÓRIA (leia antes de deduzir) ===\n"
        f"1. PREMISSA DE VARREDURA: Toda versão — em especial a PRIMEIRA iteração — "
        f"contém margem de melhoria identificável. Assuma que sim e faça DUAS passagens "
        f"sobre o texto: a primeira localiza problemas óbvios; a SEGUNDA reabre o "
        f"texto à procura de problemas sutis (ritmo, escolha léxica, conectivos, "
        f"colocações, ambiguidade, redundância). Só depois decida a dedução.\n"
        f"2. PROIBIDO `points_to_deduct: 0` COMO RESPOSTA PADRÃO: atribuir 0.0 só é "
        f"aceitável se, após a varredura dupla, você consegue citar TRECHO e afirmar "
        f"literal: 'não há nada a melhorar neste eixo'. Se não há citação concreta de "
        f"ausência de problema, o eixo NÃO foi revisado a fundo — refaça.\n"
        f"3. CALIBRAÇÃO RELATIVA: a dedução reflete a DISTÂNCIA do eixo ao seu ideal, "
        f"não o fato de o texto 'estar aceitável'. Texto 'aceitável' ≠ texto 'ótimo': "
        f"mantém dedução se sobra espaço para lapidar, mesmo que pequena.\n"
        f"4. RAZÃO + DIREÇÃO DE MELHORIA: cada `reasoning` deve (a) CITAR o trecho "
        f"exato onde está o problema e (b) PROVER uma direção concreta de como o "
        f"Redator deve lapidá-lo na próxima iteração. 'Aqui tem erro' sem remédio é "
        f"dedução inútil e será tratada como evasão.\n"
        f"5. ANTI-LENITIVO: nunca descarte problemas só para evitar penalizar — o texto "
        f"foi pago para ser lapidado, não para ser elogiado. O elogio vago custa ao "
        f"Redator a chance de evoluir; ao mesmo tempo, NUNCA invente problema que não "
        f"existe para inflar a dedução: dedução precisa sempre ter trecho citável.\n"
        f"6. PROIBIDO PERFEITISMO CEGO: deduzir é identificar desvio real, não "
        f"fabricar defeito. Se um critério verdadeiramente não merece nenhuma "
        f"dedução após a varredura, mantenha 0.0 — mas só depois de duas passagens e "
        f"com explicação explícita da ausência de problema.\n\n"
        f"IMPORTANTE: Você deve retornar OBRIGATORIAMENTE um JSON válido seguindo "
        f"exatamente este schema, cobrindo TODOS os eixos listados, sem omitir "
        f"nenhum e sem inventar IDs inexistentes:\n{schema_json_str}"
    )
