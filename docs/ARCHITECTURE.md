# ARCHITECTURE.md

## LexiCraft — Mapa de Arquitetura e Design de Sistema Técnico

Este documento define a topologia, os fluxos de dados e as diretrizes arquiteturais para o **LexiCraft**. Ele serve como fonte da verdade técnica para desenvolvedores e Agentes de IA, garantindo máxima fidelidade ao design do sistema de otimização textual agêntica.

---

## 1. Visão Geral do Sistema e Filosofia de Design

O **LexiCraft** adota a filosofia arquitetural do **Monólito Majestoso (Majestic Monolith)**, projetado para maximizar a velocidade de iteração, robustez e simplicidade de implantação, sem sacrificar a reatividade da interface de usuário ou o poder de processamento em background.

### Tech Stack Fundamental
- **Backend & Orquestração:** Django 5.x (Python 3.12+).
- **Interface Reativa (No-SPA):** Django Templates + **HTMX** + Tailwind CSS (+ Alpine.js para interações locais).
- **Processamento Agêntico & Workers:** Celery + Redis.
- **Banco de Dados:** PostgreSQL (Persistência relacional robusta).
- **Integração LLM:** Clientes assíncronos via `httpx` e validação estruturada via **Pydantic**.

### Justificativa de Desacoplamento
Devido à natureza de longa duração e alta latência das chamadas de Large Language Models (LLMs), a execução do loop agêntico (Redação $\rightarrow$ Auditoria $\rightarrow$ Matemática) não pode ocorrer na thread HTTP síncrona do Django. 
1. **Views (Django + HTMX):** Recebem comandos, despacham tarefas e realizam *polling* leve e parcial via HTMX para atualização de UI.
2. **Workers (Celery):** Assumem a carga pesada de instanciar agentes, concatenar prompts, orquestrar chamadas paralelas (`asyncio.gather`) e calcular a matemática do Nash de forma totalmente assíncrona, atualizando o banco de dados conforme progridem.

---

## 2. Diagrama de Arquitetura de Alto Nível

O fluxo de infraestrutura demonstra a separação clara entre o tráfego web/síncrono e o processamento de IA/assíncrono.

```mermaid
graph TD
    %% Nós
    U[Usuário / Navegador] 
    subgraph "Camada Web (Síncrona)"
        DW[Django Web Server\nViews & HTMX]
    end
    
    subgraph "Camada de Dados"
        DB[(PostgreSQL\nBanco Principal)]
        RD[(Redis\nBroker & Cache)]
    end
    
    subgraph "Camada Agêntica (Assíncrona)"
        CW[Celery Worker\nPipeline Orquestrador]
        ME[Math Engine\nPython Puro]
    end
    
    subgraph "Serviços Externos"
        LLM[APIs de LLMs\nOpenAI/Claude]
    end

    %% Relações
    U <-->|Requisições HTTP / Polling HTMX| DW
    DW <-->|Escrita/Leitura de UI| DB
    DW -->|Dispara Task de Otimização| RD
    RD -->|Consome Task Fila| CW
    CW <-->|Atualiza Estado/Snapshots| DB
    CW <-->|Valida Lógica [0, 1] e Nash| ME
    CW <-->|I/O Assíncrono Paralelo (httpx)| LLM
    
    classDef web fill:#10b981,stroke:#047857,stroke-width:2px,color:white;
    classDef worker fill:#3b82f6,stroke:#1d4ed8,stroke-width:2px,color:white;
    classDef db fill:#f59e0b,stroke:#b45309,stroke-width:2px,color:white;
    classDef ext fill:#6366f1,stroke:#4338ca,stroke-width:2px,color:white;
    
    class U,DW web;
    class DB,RD db;
    class CW,ME worker;
    class LLM ext;
```

---

## 3. Modelo de Dados Relacional (ERD)

O banco de dados é projetado para suportar perfis dinâmicos de $N$ eixos e rastreabilidade total de iterações através de *Snapshots*.

```mermaid
erDiagram
    USER ||--o{ TASK_EXECUTION : initiates
    PROFILE_CONFIG ||--o{ QUALITY_AXIS : contains
    PROFILE_CONFIG ||--o{ SYSTEM_PROMPT : contains
    PROFILE_CONFIG ||--o{ TASK_EXECUTION : uses
    TASK_EXECUTION ||--o{ EXECUTION_SNAPSHOT : generates
    EXECUTION_SNAPSHOT ||--o{ AUDITOR_RESULT : logs

    USER {
        int id PK
        string username
        string email
    }

    PROFILE_CONFIG {
        int id PK
        string name
        boolean is_active
    }

    QUALITY_AXIS {
        int id PK
        int profile_id FK
        string name
        float weight "Padrão 1.0 (Normalizado em runtime)"
        float base_score "Padrão 100"
        text deduction_rules
    }

    SYSTEM_PROMPT {
        int id PK
        int profile_id FK
        string role_type "WRITER | GUARDRAIL | AUDITOR_BASE"
        text content
    }

    TASK_EXECUTION {
        int id PK
        int user_id FK
        int profile_id FK
        string status "Ex: RUNNING, COMPLETED, ROLLBACK"
        text original_prompt
        float accumulated_cost_usd
        int accumulated_prompt_tokens
        int accumulated_completion_tokens
        int current_iteration
    }

    EXECUTION_SNAPSHOT {
        int id PK
        int task_execution_id FK
        int iteration_number
        text generated_text
        float nash_score "Score Global W(x)"
        json normalized_scores "Si por critério"
    }

    AUDITOR_RESULT {
        int id PK
        int snapshot_id FK
        string auditor_type "CORRETOR_1 | CORRETOR_2 | DESEMPATE"
        json deductions_payload "Validado via Pydantic"
    }
```

### Dicionário de Entidades Principais
| Entidade | Descrição Principal |
| :--- | :--- |
| `ProfileConfig` | Agrupa configurações de eixos e prompts. Permite uma experiência *out-of-the-box* ajustável. |
| `QualityAxis` | Define um critério de avaliação (Ex: Clareza), com peso bruto e regra de dedução específica. |
| `TaskExecution` | O "job" geral. Controla o estado, o teto de recursos (USD/Time/Ciclos) e tokens acumulados (Prompt vs Completion). |
| `ExecutionSnapshot` | Estado congelado de uma iteração bem-sucedida, essencial para o algoritmo de **Rollback**. |
| `AuditorResult` | Persistência do JSON validado (via Pydantic) retornado pelos agentes durante a auditoria. |

---

## 4. Diagrama de Sequência do Pipeline Agêntico

Este fluxo ilustra o loop interno executado pelo worker do Celery (`tasks.py`), englobando o Writer, o Guard-rail (3 Strikes), o Tribunal Paralelo e a avaliação matemática.

```mermaid
sequenceDiagram
    participant C as Celery Worker
    participant W as Agente Redator
    participant G as Guard-rail
    participant T as Tribunal (Corretores)
    participant M as Math Engine
    participant DB as PostgreSQL

    C->>DB: Inicia Task / Atualiza Status (RUNNING)
    
    loop Até N_max Ciclos ou Condição de Parada
        C->>W: Gera/Reescreve Texto (Prompt + Histórico)
        W-->>C: Texto Gerado
        
        Note over C, G: Loop do Guard-rail (Regra dos 3 Strikes)
        loop Máximo 3 Tentativas
            C->>G: Audita Fidelidade e Escopo
            G-->>C: Payload (Aprovado ou Falhou)
            alt Reprovado (Strike 1 ou 2)
                C->>W: Ajusta Texto com Feedback do Guard-rail
                W-->>C: Novo Texto
            else Reprovado (Strike 3)
                C->>DB: Aborta Task (ABORTED_GUARDRAIL_STRIKES)
            end
        end
        
        Note over C, T: Aprovado no Guard-rail -> Tribunal Paralelo (httpx gather)
        par Auditor 1
            C->>T: Audita Eixos (Prompt Concatendo)
            T-->>C: JSON Pydantic (Deduções 1)
        and Auditor 2
            C->>T: Audita Eixos (Prompt Concatendo)
            T-->>C: JSON Pydantic (Deduções 2)
        end
        
        C->>C: Checa Divergência (> 10%)
        opt Divergência Encontrada
            C->>T: Instancia 3º Corretor (Desempate)
            T-->>C: JSON Pydantic (Deduções 3)
        end
        
        C->>M: Envia Média das Deduções
        M-->>C: Retorna W(x) [Nash] e S_i [0.01, 1.0]
        
        C->>DB: Grava ExecutionSnapshot (Texto, Notas, JSONs)
        
        C->>C: Avalia Condição de Parada
        alt Sucesso (W >= Target)
            C->>DB: Finaliza Task (COMPLETED)
        else Estagnação (ΔW < ε) ou Estouro (Limites)
            C->>DB: Aciona ROLLBACK (COMPLETED_WITH_ROLLBACK)
        end
    end
```

---

## 5. Diagrama de Máquina de Estados das Tasks

Transições de estado do modelo `TaskExecution`, essenciais para o polling do HTMX refletir com precisão a etapa atual na interface do usuário.

```mermaid
stateDiagram
    [*] --> PENDING: View Cria Task
    PENDING --> RUNNING: Worker Celery assume
    
    state RUNNING {
        [*] --> GENERATING_TEXT
        GENERATING_TEXT --> GUARDRAIL_CHECK
        GUARDRAIL_CHECK --> GENERATING_TEXT: Retentativa (< 3 strikes)
        GUARDRAIL_CHECK --> TRIBUNAL_EVALUATION: Aprovado (Reseta strikes)
        TRIBUNAL_EVALUATION --> MATH_CALCULATION: Resolve Tribunal e Desempate
        MATH_CALCULATION --> [*]: Iteração Finalizada (Snapshot gravado)
    }
    
    RUNNING --> ABORTED_GUARDRAIL_STRIKES: Falha 3x seguidas no Guard-rail
    
    RUNNING --> COMPLETED: Nash (W) >= Target
    
    state "Avalia Rollback (Existem Snapshots?)" as CHECK_SNAPSHOTS <<choice>>
    
    RUNNING --> CHECK_SNAPSHOTS: Estagnação (ΔW < ε)
    RUNNING --> CHECK_SNAPSHOTS: Limite de Ciclos (N_max)
    RUNNING --> CHECK_SNAPSHOTS: Estouro Orçamento (C_max)
    RUNNING --> CHECK_SNAPSHOTS: Estouro Limite Tempo (T_max)
    
    CHECK_SNAPSHOTS --> COMPLETED_WITH_ROLLBACK: Sim (Recupera maior W)
    CHECK_SNAPSHOTS --> FAILED_NO_SNAPSHOTS: Não (Falha no ciclo 1)
    
    COMPLETED --> [*]
    COMPLETED_WITH_ROLLBACK --> [*]
    ABORTED_GUARDRAIL_STRIKES --> [*]
    FAILED_NO_SNAPSHOTS --> [*]
```

---

## 6. Arquitetura do Motor Matemático e Isocusto

Para garantir previsibilidade total e evitar alucinações matemáticas de LLMs, a lógica numérica foi rigidamente desacoplada do prompt e isolada no `math_engine.py`.

### A. Algoritmo da Barganha de Nash Assimétrica
Os agentes (Tribunal) não dão notas finais; eles apontam **deduções absolutas** baseadas no JSON de infrações. O Python executa os cálculos:

1. **Normalização de Pesos:**
   $$w_i = \frac{\text{peso}_i}{\sum \text{pesos}}$$
2. **Cálculo da Nota Bruta:**
   $$\text{Bruta}_i = \max(0, \text{Base}_i - \sum \text{Deduções}_i)$$
3. **Normalização Rígida de Critérios ($S_i$):**
   $$S_i = \max\left(0.01, \frac{\text{Bruta}_i}{\text{Base}_i}\right)$$
   *(Nota: O piso absoluto de $0.01$ garante que o colapso de um único critério não zere toda a equação de Nash).*
4. **Pontuação Global (Produto de Nash $W$):**
   $$W(x) = \prod_{i=1}^{n} (S_i)^{w_i}$$

### B. Gestão de Isocusto e Tokens
O orquestrador Celery envolve todas as chamadas de API (`Writer`, `Guardrail`, `Auditor`) com um utilitário que inspeciona a resposta de utilização de tokens (`prompt_tokens` e `completion_tokens`).
* **Custos:** O custo é estimado com base em uma tabela estática por tipo de token (Ex: Custo/1M Prompt, Custo/1M Completion).
* **Parada Emergencial:** Ao final de cada etapa, `task.accumulated_cost_usd` é atualizado. Se $\ge C_{max}$, a tarefa interrompe o loop e aciona a rotina de Rollback.

---

## 7. Estratégia de Resiliência e Rollback

O **Rollback** é o mecanismo de segurança que garante que o usuário nunca saia de mãos vazias se o pipeline estagnar ou atingir o teto de recursos.

Quando acionado (por $\Delta W < \epsilon$, $N_{max}$, $C_{max}$ ou $T_{max}$), o orquestrador não descarta o progresso. Ele consulta o histórico relacional:

```python
# Lógica encapsulada no Serviço de Otimização (Celery Task)
def execute_rollback(task_execution: TaskExecution) -> None:
    best_snapshot = task_execution.snapshots.order_by('-nash_score').first()
    
    if best_snapshot:
        task_execution.final_text = best_snapshot.generated_text
        task_execution.final_score = best_snapshot.nash_score
        task_execution.status = 'COMPLETED_WITH_ROLLBACK'
    else:
        # Ocorre apenas se atingir o limite antes de completar a iteração 1
        task_execution.status = 'FAILED_NO_SNAPSHOTS'
        
    task_execution.save()
```

---

## 8. Segurança, Validação e Variáveis de Ambiente

### A. Esquemas de Validação (Anti-Alucinação e Prompt Injection)
1. **Pydantic Strict Mode:** As saídas do Tribunal e do Guard-rail usam `response_format` ou *Function Calling* atrelados a schemas rigorosos do Pydantic (listados no `AGENTS.md`). Se o LLM alucinar a estrutura, a biblioteca levanta erro e o Orquestrador realiza *retry* isolado antes de falhar.
2. **Mitigação de Prompt Injection:** O texto original fornecido pelo usuário deve ser delimitado estruturalmente no prompt (ex: tag `<user_input>`) e enviado no papel `user`, enquanto as regras de eixos, pesos e comportamento dos agentes residem puramente no papel `system`, blindando as instruções basilares.

### B. Mapa de Variáveis de Ambiente Essenciais (`.env`)
```bash
# Core Django
SECRET_KEY="sua-chave-criptografica"
DEBUG=False
ALLOWED_HOSTS="localhost,127.0.0.1,dominio.com"

# Persistência e Broker
DATABASE_URL="postgres://user:pass@localhost:5432/lexicraft"
REDIS_URL="redis://localhost:6379/0"
CELERY_BROKER_URL=${REDIS_URL}

# Provedores de Large Language Models
OPENAI_API_KEY="sk-..."
ANTHROPIC_API_KEY="sk-ant-..."

# Parametrização Global de Limites de Sistema (Fallback)
MAX_BUDGET_USD_PER_TASK=2.50
MAX_TIME_SECONDS_PER_TASK=300
```
