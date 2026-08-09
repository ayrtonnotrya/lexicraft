# AGENTS.md — Diretrizes Mestras de Desenvolvimento para Agentes de IA

Este documento contém a arquitetura, regras de negócio, convenções de código e padrões operacionais do projeto **LexiCraft**. Ele foi projetado para orientar Agentes de IA (como Cursor, Claude Code, Devin, GitHub Copilot) na geração, refatoração e manutenção contínua do código-fonte com máxima precisão e fidelidade arquitetural.

---

## 1. Visão Geral e Objetivo do LexiCraft

O **LexiCraft** é uma plataforma web Full-Stack e motor agêntico autônomo operando em loop fechado alimentado por Large Language Models (LLMs). Sua finalidade é executar uma "linha de montagem" de otimização textual, capaz de redigir, auditar, pontuar e reescrever textos até atingirem o nível ótimo de qualidade.

### Destaques do Sistema
- **Perfis Customizáveis Out-of-the-Box:** Gerenciamento dinâmico de $N$ eixos de qualidade, pesos, pontuações base e prompts.
- **Pipeline Agêntico Triplo:** Agente Redator $\rightarrow$ Agente Guard-rail (Fidelidade/Escopo) $\rightarrow$ Tribunal Paralelo de Corretores.
- **Motor Matemático Determinístico:** Avaliação rigorosa no intervalo $[0, 1]$ utilizando a **Barganha de Nash Assimétrica**.
- **Mecanismos de Resiliência:** Regra dos 3 Strikes no Guard-rail (com reset automático ao passar), desempate via 3º Corretor, controle rigoroso de tokens/orçamento/tempo e Rollback automático para o melhor Snapshot gravado.

---

## 2. Tech Stack Recomendada (Django Full-Stack)

A arquitetura adota a filosofia do **Monólito Majestoso (Majestic Monolith)** com reatividade moderna no backend, priorizando simplicidade de implantação, robustez e performance.

* **Linguagem:** Python 3.12+
* **Framework Web:** Django 5.x (Full-Stack Monolith)
* **Interface Reativa:** Django Templates + HTMX + Tailwind CSS (com Alpine.js para pequenas interações de UI no client-side). **NÃO utilizar React, Vue, Angular ou frameworks SPA.**
* **Processamento Assíncrono / Background Workers:** Celery + Redis (para orquestrar loops agênticos de longa duração sem bloquear threads HTTP).
* **Cliente HTTP Assíncrono:** `httpx` (para chamadas paralelas de API de LLMs).
* **ORM e Banco de Dados:** Django ORM + PostgreSQL (SQLite permitido para desenvolvimento local e suíte de testes).
* **Validação de Payloads de IA:** Pydantic  (para parsing e validação rigorosa dos JSONs retornados pelos LLMs).
* **Suíte de Testes:** Pytest-django + `unittest.mock` (para simulação determinística de chamadas LLM).

---

## 3. Estrutura de Diretórios do Projeto Django

O código deve seguir rigidamente a estrutura modular dividida por aplicações do Django (`apps/`):

```text
lexicraft/
├── manage.py
├── requirements.txt
├── pytest.ini
├── .env.example
├── config/
│   ├── __init__.py
│   ├── settings/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── local.py
│   │   └── production.py
│   ├── urls.py
│   ├── celery.py
│   └── wsgi.py
├── apps/
│   ├── core/                      # Utilitários compartilhados, mixins e modelos base
│   │   ├── models.py
│   │   └── utils.py
│   ├── profiles/                  # Gestão de Perfis, Eixos de Qualidade e Prompts
│   │   ├── models.py              # ProfileConfig, QualityAxis, SystemPrompt
│   │   ├── admin.py
│   │   ├── forms.py
│   │   └── views.py
│   ├── orchestrator/              # Coração Agêntico (Tasks Celery, Agentes e Math Engine)
│   │   ├── tasks.py               # Celery Tasks (Loop do Pipeline)
│   │   ├── models.py              # TaskExecution, ExecutionSnapshot, AuditorResult
│   │   ├── agents/                # LLM Clients & Abstrutores
│   │   │   ├── writer.py          # Agente Redator
│   │   │   ├── guardrail.py       # Agente Guard-rail
│   │   │   └── auditor.py         # Agentes Corretores Paralelos (Async httpx)
│   │   ├── services/
│   │   │   ├── math_engine.py     # Motor Python Puro: Nash Bargaining, Normalização [0,1]
│   │   │   └── prompt_builder.py  # Concatenação dinâmica de prompts de auditoria
│   │   └── schemas.py             # Schemas Pydantic  para respostas estruturadas de IA
│   └── dashboard/                 # Frontend HTMX / Views do Painel
│       ├── views.py
│       └── urls.py
├── templates/                     # Django Templates Monolíticos
│   ├── base.html
│   ├── dashboard/
│   │   ├── index.html
│   │   └── task_detail.html
│   └── partials/                  # Fragmentos renderizados via HTMX
│       ├── profile_form.html
│       ├── task_progress.html
│       └── snapshot_card.html
└── static/                        # CSS compilado (Tailwind), JS estático e assets
```

---

## 4. Padrões de Código e Diretrizes Django

### A. Interface e Views (Django Templates + HTMX)
* Utilize **Class-Based Views (CBVs)** ou **Function-Based Views (FBVs)** curtas e especializadas.
* Quando uma requisição for iniciada por HTMX (`request.headers.get('HX-Request')`), a view DEVE retornar um fragmento parcial (`partials/*.html`), reduzindo o payload de rede.
* As telas principais do `dashboard/` devem permitir acionar execuções de otimização textual via POST e monitorar o progresso em tempo real através de polling HTMX (`hx-get` com `hx-trigger="every 2s"`).

### B. Gestão de Perfis no Django Admin
* Todos os modelos da app `profiles` (`ProfileConfig`, `QualityAxis`, `SystemPrompt`) devem estar totalmente visíveis e manipuláveis no Django Admin.
* Permita ao usuário cadastrar **$N$ Eixos de Qualidade** vinculados a um Perfil (sem limite fixo).
* Na alteração de pesos no admin ou via UI, execute a validação no formulário para garantir normalização runtime ($\sum w_i = 1.0$).

### C. Desacoplamento do Motor Matemático (`math_engine.py`)
* **NUNCA** solicite ao LLM que realize cálculos aritméticos, multiplicações de pesos ou normalização de notas.
* A matemática do projeto deve ser $100\%$ determinística e encapsulada em `apps/orchestrator/services/math_engine.py`.

#### Especificação do Algoritmo em `math_engine.py`:
```python
import math
from typing import List, Dict, Any, TypedDict

class CriterionScore(TypedDict):
    axis_id: int
    base_score: float
    weight: float
    deductions: float

def calculate_nash_bargaining(criteria: List[CriterionScore], s_min: float = 0.01) -> Dict[str, Any]:
    """
    Calcula a Nota Bruta, Normalização Rígida [0, 1] e a Barganha de Nash Assimétrica W(x).
    
    Regras:
    1. Pesos são normalizados: w_i = weight_i / sum(weights)
    2. Nota_Bruta_i = max(0.0, Base_i - Sum_Deductions_i)
    3. S_i = max(s_min, min(1.0, Nota_Bruta_i / Base_i))
    4. W(x) = Product(S_i ^ w_i)
    """
    if not criteria:
        raise ValueError("A lista de critérios não pode estar vazia.")

    total_weight = sum(c['weight'] for c in criteria)
    if total_weight <= 0:
        raise ValueError("A soma dos pesos deve ser maior que zero.")

    normalized_scores: Dict[int, float] = {}
    raw_scores: Dict[int, float] = {}
    normalized_weights: Dict[int, float] = {}
    
    nash_product = 1.0

    for item in criteria:
        axis_id = item['axis_id']
        w_i = item['weight'] / total_weight
        normalized_weights[axis_id] = w_i
        
        # Garante que as deduções não resultem em nota menor que zero
        raw_score = max(0.0, item['base_score'] - item['deductions'])
        raw_scores[axis_id] = raw_score
        
        # S_i normalizado no intervalo rígido [s_min, 1.0]
        s_i = max(s_min, min(1.0, raw_score / item['base_score']))
        normalized_scores[axis_id] = s_i
        
        # Acumulador da Barganha de Nash Assimétrica
        nash_product *= math.pow(s_i, w_i)

    return {
        "nash_score": round(nash_product, 6),
        "normalized_scores": normalized_scores,
        "raw_scores": raw_scores,
        "normalized_weights": normalized_weights
    }
```

---

## 5. Regras de Negócio Críticas para o Worker (Celery/Orquestrador)

Toda a orquestração do loop deve ser executada de forma assíncrona na tarefa Celery `apps/orchestrator/tasks.py:run_optimization_pipeline(task_execution_id: int)`.

### A. Rastreamento de Consumo de Tokens e Custo Financeiro
Todo wrapper de chamada de API para LLM (Redator, Guard-rail, Corretores) DEVE capturar obrigatoriamente:
* `prompt_tokens`
* `completion_tokens`
* `total_tokens`

A tarefa do Celery calcula o custo estimado em USD com base no modelo utilizado e atualiza os campos acumulados no modelo `TaskExecution`:
* `task_execution.accumulated_prompt_tokens += prompt_tokens`
* `task_execution.accumulated_completion_tokens += completion_tokens`
* `task_execution.accumulated_cost_usd += estimated_cost`

Se `accumulated_cost_usd >= max_budget_usd`, a tarefa aciona o **Rollback e encerra por estouro de orçamento**.

### B. Fluxo Operacional Detalhado
1. **Ativação:** A view recebe a solicitação, cria o registro `TaskExecution` (status=`PENDING`) e dispara a tarefa Celery.
2. **Ciclo de Iteração ($n = 1 \dots N_{max}$):**
   * **Passo 1: Agente Redator:** Gera/reescreve o texto. Se $n > 1$, o prompt do redator recebe obrigatoriamente: o texto da versão anterior, a mensagem original e o JSON de infrações detalhadas da iteração anterior.
   * **Passo 2: Guard-rail (Fidelidade e Escopo):**
     - O Guard-rail analisa se houve alucinação, esquecimento de diretrizes ou fuga do objetivo primário em relação à mensagem original.
     - **Regra dos 3 Strikes com Reset:** O Redator tem até 3 tentativas seguidas **dentro da mesma iteração** para passar no Guard-rail. Um Strike é consumido tanto por reprovação semântica do Guard-rail (`is_approved=False`) quanto por qualquer exceção de infraestrutura que impeça a conclusão limpa do step: erros de I/O de rede via `httpx`/`AsyncOpenAI` (Rate Limit `429`, `httpx.TimeoutException`, `httpx.ConnectError`, Erro `500`), abortos de parse do schema dinâmico do Pydantic (`ValidationError` por `axis_id` alucinado ou critério omitido) ou falhas no contrato do Redator. Se reprovar na 1ª ou 2ª tentativa, incrementa o contador de strikes da iteração, aplica *backoff* controlado e devolve o feedback do Guard-rail (ou a mensagem de erro de infraestrutura) ao Redator para retentativa — sem nunca propagar a exceção ao Worker do Celery. Se for **APROVADO**, o contador de strikes é zerado para as próximas iterações. Se falhar pela **3ª vez consecutiva** (seja por motivo semântico, de rede ou de schema), a tarefa é interrompida imediatamente, atualizando o status para `ABORTED_GUARDRAIL_STRIKES` e registrando a justificativa da falha.
   * **Passo 3: Tribunal de Corretores Paralelos (`httpx` + `asyncio.run`):**
     - O orquestrador executa 2 Corretores em paralelo usando `httpx.AsyncClient` encapsulado em `asyncio.run(asyncio.gather(...))`.
     - Cada corretor retorna um JSON estrito (validado via Pydantic ) contendo a lista de deduções por eixo.
     - **Fórmula de Divergência:** O código calcula a divergência relativa de deduções para cada critério $i$:
       $$\text{Divergência}_i = \frac{|\text{Dedução\_Corretor\_1}_i - \text{Dedução\_Corretor\_2}_i|}{\text{Pontuação\_Base}_i}$$
     - Se $\text{Divergência}_i > 0.10$ ($10\%$) em *qualquer* critério, o orquestrador aciona automaticamente um **3º Corretor de Desempate**.
     - A dedução final por critério será a **média matemática** das pontuações dos corretores acionados (2 ou 3).
   * **Passo 4: Motor Matemático (Código Pure Python):**
     - Passa os resultados consolidados para `calculate_nash_bargaining()`.
     - Obtém $S_i \in [0.01, 1.0]$ e o Score de Nash $W(x)$.
   * **Passo 5: Gravação de Snapshot:**
     - Salva um registro em `ExecutionSnapshot` com o número do ciclo, texto gerado, notas $S_i$, $W(x)$, tokens consumidos no ciclo e o histórico de JSON dos corretores.
* **Passo 6: Avaliação das Condições de Parada:**
      1. **Sucesso (Convergência):** Se $W(x) \ge Target$ (ex: $0.95$), finaliza com sucesso (`COMPLETED`).
      2. **Ganho Nulo ($\Delta W < \epsilon$):** Se $W_t - W_{t-1} < \epsilon$ (ex: $< 0.02$), a otimização estagnou. Executa **Rollback** e entrega o melhor snapshot.
      3. **Degradação Sumária ($\Delta W < 0$):** Se o ganho marginal for negativo ($W_t - W_{t-1} < 0$, isto é, o LLM piorou o texto em relação ao ciclo anterior), o orquestrador aborta a tarefa instantaneamente, aplicando **Rollback** imediato para o melhor snapshot histórico. Não há retentativa: degradação é tratada como estagnação severa e irrecuperável, encerrando o loop e ejetando a melhor versão observada.
      4. **Estouro de Tetos ($C_{max}, T_{max}, N_{max}$):** Se exceder orçamento em USD, tempo limite em segundos ou número máximo de ciclos, interrompe o loop, executa **Rollback** e entrega o melhor snapshot. O teto de tempo $T_{max}$ é calculado exclusivamente contra o campo `started_at` (instante da transição `PENDING -> RUNNING`) e o tempo corrente `now()`, jamais contra `created_at`, de modo que o tempo de fila do *broker* do Celery nunca penalize o usuário.

### C. Lógica de Rollback
Quando o pipeline atinge um encerramento por estagnação ($\Delta W < \epsilon$) ou estouro de limites ($C_{max}, T_{max}, N_{max}$), o orquestrador executa a query de Rollback no ORM:
```python
best_snapshot = task_execution.snapshots.order_by('-nash_score').first()
if best_snapshot:
    task_execution.final_text = best_snapshot.generated_text
    task_execution.final_score = best_snapshot.nash_score
    task_execution.status = 'COMPLETED_WITH_ROLLBACK'
else:
    task_execution.status = 'FAILED_NO_SNAPSHOTS'
task_execution.save()
```

### D. Comunicação de Progresso com o Frontend
* O modelo `TaskExecution` possui os campos `current_step` (ex: "Executando Guard-rail (Tentativa 2/3)", "Avaliando Tribunal de Corretores", "Calculando Nash") e `current_iteration`.
* O frontend HTMX consulta periodicamente o endpoint parcial `/tasks/<id>/status/` que renderiza o progresso atualizado sem recarregar a página.

### E. Garbage Collector de Tarefas Zumbis (Ceifador)
* Um *beat schedule* do Celery (`apps/orchestrator/tasks.py:reap_zombie_tasks`) é cronometrado para executar de 1 em 1 minuto.
* A tarefa varre o banco por execuções `RUNNING` cujo campo `last_heartbeat_at` esteja desatualizado há mais de 1 minuto em relação a `now()` — situação característica de um Worker morto, reiniciado ou ejetado por OOM no meio do loop.
* Cada tarefa zumbis identificada é convertida para `status=FAILED_TIMEOUT` e o melhor `ExecutionSnapshot` histórico é preservado em `final_text`/`final_score` via a mesma query de *Rollback*, garantindo que o trabalho já consolidado não se perca pelo colapso do processo.

---

## 6. Schemas Pydantic para Validação de Output de IA

Para evitar retornos corrompidos ou mal formatados dos LLMs, todas as chamadas de auditoria dos corretores DEVEM utilizar validação via Pydantic . O schema do Corretor não é uma classe estática: ele é gerado em *runtime* pela fábrica `build_dynamic_auditor_schema(valid_axis_ids)`, que trava o `axis_id` em um `Literal` exato dos IDs do Perfil em execução e impõe um `@field_validator('deductions')` garantindo coincidência integral com o `valid_axis_ids` (nenhum ID alucinado, nenhum critério omitido).

> **Compatibilidade OpenCode Go (Universal JSON Mode):** Por operarmos com o provedor **OpenCode Go**, **NÃO** utilize o método `.parse()` da OpenAI, o *Function Calling* atrelado a schema, nem a flag `strict: true` (esses recursos geram `400 Bad Request` em modelos open-source). Em vez disso, TODAS as chamadas devem usar o **Universal JSON Mode** (`response_format={"type": "json_object"}`), injetando o JSON Schema no prompt do sistema e validando manualmente a string de resposta com o Pydantic: `Schema.model_validate_json(response.content)`. Essa integração é 100% compatível com qualquer endpoint OpenAI-Compatible.

```python
from pydantic import BaseModel, Field, field_validator, ValidationError
from typing import List, Type, Literal

def build_dynamic_auditor_schema(valid_axis_ids: List[int]) -> Type[BaseModel]:
    AxisIdLiteral = Literal[tuple(valid_axis_ids)]

    class DeductionItem(BaseModel):
        axis_id: AxisIdLiteral = Field(description="ID exato do eixo de qualidade avaliado")
        criterion_name: str = Field(description="Nome do critério (ex: Clareza, Tom Humano)")
        points_to_deduct: float = Field(ge=0.0, description="Quantidade absoluta de pontos a deduzir")
        reasoning: str = Field(description="Explicação detalhada e trecho do texto onde ocorreu a infração")

    required_ids = set(valid_axis_ids)

    class AuditorResponseSchema(BaseModel):
        summary: str = Field(description="Resumo executivo da auditoria do texto")
        deductions: List[DeductionItem] = Field(description="Lista de infrações encontradas e suas deduções")

        @field_validator('deductions')
        @classmethod
        def _ensure_full_coverage(cls, deductions: List[DeductionItem]) -> List[DeductionItem]:
            if {item.axis_id for item in deductions} != required_ids:
                raise ValueError("O conjunto de axis_id retornados não cobre exatamente o conjunto esperado.")
            return deductions

    return AuditorResponseSchema
```

---

## 7. Diretrizes de Testes

Toda alteração ou nova funcionalidade DEVE vir acompanhada de testes unitários e de integração utilizando `pytest-django`.

1. **Testes do Motor Matemático (`tests/test_math_engine.py`):**
   - Testar normalização de pesos com soma diferente de 1.
   - Testar colapso de notas zeradas (garantir que $S_{min} = 0.01$ evita produto zero).
   - Testar cálculo determinístico do score de Nash $W(x)$.
2. **Testes de Integração dos Agentes e Celery (`tests/test_pipeline.py`):**
   - Utilizar Mocks (`unittest.mock.patch`) para simular chamadas de API das LLMs.
   - Testar os **3 Strikes do Guard-rail** (forçar 3 falhas seguidas e verificar o status `ABORTED_GUARDRAIL_STRIKES`).
   - Testar o **Reset de Strikes** quando o Guard-rail é aprovado na 2ª tentativa.
   - Testar que **falhas de infraestrutura** (`httpx.TimeoutException`, Rate Limit `429` e Erro `500`) consomem 1 Strike cada sem quebrar o Worker do Celery.
   - Testar que o **schema dinâmico do Pydantic** rejeita `axis_id` alucinados ou critérios omitidos, gerando `ValidationError` que consome 1 Strike.
   - Testar a **Degradação Sumária** ($\Delta W < 0$) acionando Rollback imediato à iteração anterior, sem retentativa.
   - Testar a **fórmula de divergência** e o acionamento condicional do **3º Corretor** quando divergência $> 10\%$.
   - Testar o rastreamento de **tokens e custo em USD** por ciclo.
   - Testar a lógica de **Rollback** selecionando a versão com maior $W(x)$ do histórico.
   - Testar o **Ceifador de Tarefas Zumbis** (`reap_zombie_tasks`): execuções `RUNNING` com `last_heartbeat_at` desatualizado há mais de 1 minuto devem virar `FAILED_TIMEOUT` preservando o melhor snapshot.
3. **Testes de Views e Endpoints HTMX (`tests/test_views.py`):**
   - Garantir que requisições com header `HX-Request: true` retornem os fragmentos HTML esperados (`partials/`).

---

## 8. Regras de "Do's and Don'ts" do Desenvolvedor

### DO's (O que FAZER):
* **FAÇA** o parse e validação de todos os retornos JSON de LLMs utilizando schemas Pydantic .
* **FAÇA** o rastreamento rigoroso de `prompt_tokens` e `completion_tokens` em cada chamada de LLM para atualizar o custo financeiro acumulado.
* **FAÇA** o isolamento total da execução do loop agêntico em tarefas assíncronas do Celery.
* **FAÇA** chamadas de API paralelas de LLMs no tribunal usando `httpx.AsyncClient` com `asyncio.run(asyncio.gather(...))` dentro das tasks do Celery.
* **FAÇA** o armazenamento estrito de cada iteração na tabela `ExecutionSnapshot` para auditoria e histórico de evolução.
* **FAÇA** a separação limpa das responsabilidades: Views gerenciam HTTP/HTMX, Celery gerencia orquestração, Pydantic gerencia validação e `math_engine.py` gerencia a matemática.
* **FAÇA** o uso do **Universal JSON Mode** (`response_format={"type": "json_object"}`) com o JSON Schema injetado no prompt do sistema e validação manual via `Schema.model_validate_json(response.content)`, garantindo compatibilidade total com o provedor **OpenCode Go** e qualquer endpoint OpenAI-Compatible.

### DON'Ts (O que NÃO FAZER):
* **NÃO utilize** o método `.parse()` da OpenAI, *Function Calling* atrelado a schema ou a flag `strict: true`. Esses recursos são incompatíveis com os modelos Open-Source do **OpenCode Go** e geram `400 Bad Request`. Sempre valide manualmente a string JSON com Pydantic.
* **NÃO execute chamadas de LLM de longa duração dentro da thread de requisição HTTP síncrona do Django.** Use sempre tarefas assíncronas do Celery.
* **NÃO coloque regras de negócio matemáticas ou ponderação de pesos dentro dos prompts do LLM.** O LLM apenas aponta as infrações e deduções brutas; o código Python calcula a nota final.
* **NÃO crie um frontend React, Vue ou Single Page Application (SPA) separado.** Mantenha a simplicidade arquitetural com Django Templates + HTMX + Tailwind CSS.
* **NÃO hardcode prompts no código-fonte.** Prompts base, subprompts de eixos e diretrizes do guard-rail devem ser armazenados no banco de dados e gerenciáveis via admin/interface.
* **NÃO permita que erros não tratados na API do LLM quebrem o Worker do Celery.** Implemente blocos de captura com *retries* controlados e log estruturado.

---

## 9. Execução de Comandos via Docker (Regra Obrigatória)

O LexiCraft roda, em desenvolvimento e produção, **sempre via Docker Compose** (serviços `web`, `worker`, `beat`, `db` em Postgres, `redis`). O banco de verdade é o Postgres do container, **não** o `db.sqlite3` local da raiz.

### A. Verifique o Docker ANTES de qualquer comando que toque banco/infraestrutura
Antes de rodar `migrate`, `seed_profiles`, `collectstatic`, scripts de dados ou qualquer comando `manage.py` que leia/escreva no banco, o agente DEVE:
1. Confirmar que os containers estão de pé: `docker compose ps`.
2. Executar o comando **dentro** do container `web`: `docker compose exec -T web python manage.py <comando>`.
3. NUNCA rodar esses comandos no `.venv` local — eles operariam sobre o `db.sqlite3` local, divergindo do ambiente real.

### B. Exemplos de execução correta
```bash
docker compose ps
docker compose exec -T web python manage.py migrate
docker compose exec -T web python manage.py seed_profiles
docker compose exec -T web python manage.py collectstatic --noinput
```

### C. Quando o ambiente roda fora do Docker
Exceção: a suíte de testes (`pytest`) usa `pytest-django` com SQLite e pode rodar no `.venv` local, pois é isolada do banco de produção. Qualquer comando com efeito persistente no banco do app DEVE ir pelo Docker.

### D. Se o Docker não estiver rodando
Se `docker compose ps` não mostrar os containers ativos, **NÃO** despeje comandos `manage.py` no `.venv` local como substituto silencioso. Avise o usuário e pergunte se ele quer subir a stack (`docker compose up -d --build`) antes de prosseguir.
