# TEST_SCENARIOS.md

## A Bíblia de Testes Automatizados do LexiCraft

Este documento atua como a especificação absoluta e o guia de referência para a suíte de testes do **LexiCraft**. Ele adota as práticas de *Test-Driven Development* (TDD) e *Behavior-Driven Development* (BDD) aplicadas ao ecossistema Django, Celery e integrações de IA Assíncronas. Todos os Agentes Codificadores (AI) e Engenheiros de Software devem seguir rigorosamente estes cenários e diretrizes para garantir a cobertura de código, a integridade matemática e a resiliência operacional do orquestrador.

---

## 1. Filosofia de Testes (TDD e Mocks)

1. **Determinismo Absoluto:** Testes automatizados não possuem estocasticidade. O comportamento de "adivinhação" ou variabilidade natural dos Large Language Models (LLMs) não deve, em hipótese alguma, chegar à esteira de testes (CI/CD).
2. **A Regra de Ouro (Zero Network):** **NENHUM teste automatizado deve realizar requisições HTTP reais para APIs da OpenAI, Anthropic ou qualquer outro provedor.** Qualquer I/O de rede acionado dentro do diretório `tests/` resultará em falha imediata da pipeline.
3. **Mocks Estruturados Pydantic:** Em vez de mockar dicionários arbitrários (que podem esconder erros de schema), todos os mocks de IA devem retornar instâncias validadas das classes Pydantic definidas em `LLM_SCHEMAS.md` (ex: `WriterResponseSchema`, `AuditorResponseSchema`).
4. **Isolamento BDD:** Cada cenário testa uma mudança de estado ou um cálculo. O ecossistema Django (`pytest-django`) deve ser manipulado via fixtures transacionais (`@pytest.mark.django_db(transaction=True)` quando testar Workers/Celery).

---

## 2. Especificação BDD para o Motor Matemático (`math_engine.py`)

A suíte de testes de `tests/test_math_engine.py` não precisa do Django DB. Trata-se de Python puro testando as fronteiras numéricas.

### Cenário 1: Pontuação Perfeita (Base Padrão)
* **Dado** um perfil com 3 eixos de qualidade, todos com pontuação base `100` e peso `1.0`.
* **E** deduções consolidadas pelo tribunal de `[0, 0, 0]`.
* **Quando** o motor matemático `calculate_nash_bargaining` processar as notas.
* **Então** a nota bruta de todos os eixos deve ser `100.0`.
* **E** as notas normalizadas ($S_i$) devem ser `[1.0, 1.0, 1.0]`.
* **E** a Pontuação de Nash Global $W(x)$ resultante deve ser estritamente `1.000000`.

### Cenário 2: Tratamento de Borda e Colapso Catastrófico ($S_{min}$)
* **Dado** um cenário de otimização de 2 eixos (ambos com base `100`, peso `1.0`).
* **E** o Eixo 1 recebe `0` deduções, mas o Eixo 2 recebe `150` pontos de dedução.
* **Quando** o motor calcular a nota bruta.
* **Então** a nota bruta do Eixo 2 não deve ser negativa, assumindo `0.0` cravado.
* **Quando** o motor calcular a nota normalizada.
* **Então** o Eixo 2 deve ser limitado pelo piso de segurança, resultando em $S_2 = 0.010000$.
* **E** o Eixo 1 deve possuir $S_1 = 1.000000$.
* **E** o $W(x)$ final deve ser `0.100000` (raiz quadrada de 0.01).

### Cenário 3: Nash Assimétrico vs Média (Diferença de Penalidade)
* **Dado** um cenário de 2 eixos simétricos em peso e base (`100`).
* **E** o Eixo 1 perde `10` pontos ($S_1 = 0.90$) e o Eixo 2 perde `80` pontos ($S_2 = 0.20$).
* **Quando** o motor executar a barganha de Nash.
* **Então** o score global $W(x)$ deve ser `0.424264`.
* *(Comentário: Isso garante que o sistema prioriza o Nash e não a Média Aritmética Ingênua de 0.55).*

### Cenário 4: Pesos Diferentes e Distribuição Múltipla
* **Dado** que o Eixo 1 tem peso nominal `2.0` (dedução `10`, base `100`).
* **E** o Eixo 2 tem peso nominal `1.0` (dedução `20`, base `100`).
* **Quando** os pesos forem normalizados internamente.
* **Então** $w_1$ deve equivaler a `0.666667` e $w_2$ a `0.333333`.
* **E** a Pontuação de Nash $W(x)$ deve ser `0.865350`.

### Cenário 5: Avaliação de Divergência do Tribunal
* **Dado** que o Corretor 1 deduziu `10` pontos no Eixo 1 e o Corretor 2 deduziu `25` pontos.
* **E** o Limiar de Divergência está configurado para `0.10` ($10\%$).
* **Quando** a função `evaluate_tribunal_divergence` for invocada com base de `100`.
* **Então** a divergência relativa será calculada como `0.15` ($15\%$).
* **E** a função deve retornar obrigatoriamente `True` (acionando o 3º Corretor).

---

## 3. Especificação BDD para o Pipeline Agêntico (Celery Task)

Este arquivo de testes (`tests/test_pipeline.py`) lidará com as tarefas do Celery e as transições de estado (modelos do Django). Utiliza-se *AsyncMocks* para interceptar os passos do orquestrador.

### Cenário A: Fluxo Perfeito (Golden Path)
* **Dado** que uma Task Celery é iniciada com `status=PENDING`.
* **Quando** a execução iniciar, ela deve transitar para `RUNNING`.
* **E** o Agente Redator gerar o primeiro rascunho com sucesso.
* **E** o Agente Guard-rail retornar `is_approved=True` na 1ª tentativa.
* **E** o Tribunal (Corretor 1 e 2) retornar avaliações idênticas (divergência `0%`).
* **E** o $W(x)$ retornado pelo motor for `0.98` (sendo o *Target* do sistema $0.95$).
* **Então** a tarefa deve salvar o primeiro Snapshot.
* **E** deve atualizar a Task para `status=COMPLETED`.
* **E** o campo `final_text` deve conter o texto gerado.

### Cenário B: Resiliência do Guard-rail (Os 3 Strikes e Reset)
* **Dado** um pipeline executando a Iteração 1.
* **Quando** o Redator envia o texto para o Guard-rail e o mock do Guard-rail retorna `is_approved=False`.
* **Então** o contador de strikes deve ir para `1` e o Redator deve ser reacionado.
* **Quando** o Guard-rail reprova novamente (`is_approved=False`).
* **Então** o contador de strikes deve ir para `2`.
* **Quando** o Redator reescreve e envia pela 3ª vez, e o Guard-rail retorna `is_approved=True`.
* **Então** o contador de strikes deve ser resetado para `0` para a próxima iteração.
* **E** o texto deve avançar para o Tribunal de Corretores.

### Cenário C: Aborto Irrecuperável por Falha Crítica de Escopo
* **Dado** que um texto gerado entra no Loop do Guard-rail.
* **Quando** o mock do Guard-rail retornar `is_approved=False` por 3 tentativas consecutivas na mesma iteração.
* **Então** a Task Celery deve encerrar o loop imediatamente.
* **E** o modelo da Task no banco de dados deve assumir `status=ABORTED_GUARDRAIL_STRIKES`.
* **E** nenhum `ExecutionSnapshot` deve ser criado para essa iteração mal-sucedida.

### Cenário D: Instanciação do 3º Corretor no Tribunal
* **Dado** que o pipeline superou o Guard-rail e iniciou o Tribunal.
* **Quando** o Corretor 1 retorna uma infração de `10` pontos e o Corretor 2 retorna uma infração de `40` pontos para o mesmo eixo.
* **Então** a divergência avaliada será de $30\%$, o que é maior que o limiar estipulado ($10\%$).
* **E** o orquestrador deve instanciar uma chamada paralela para o mock do Corretor de Desempate (3º Corretor).
* **E** o banco de dados deve gravar rigorosamente **três instâncias** de `AuditorResult` para este snapshot (uma para cada corretor).
* **E** a lista de notas passada em memória para o Motor Matemático (`math_engine.py`) deve refletir a **média matemática estrita** dos três corretores (ex: se o 3º deu `25`, a média inserida na equação de Nash será $10+40+25 / 3 = 25$).

### Cenário E: Acionamento de Rollback por Teto Orçamentário ($C_{max}$)
* **Dado** que uma tarefa completou o Ciclo 1 gravando um Snapshot de $W(x) = 0.80$.
* **E** ela possui um teto de custo ($C_{max}$) de `$2.50`.
* **Quando** o ciclo 2 iniciar e a simulação de uso de tokens acumular `$2.55` em `accumulated_cost_usd`.
* **Então** a verificação de Isocusto deve disparar a interrupção de segurança.
* **E** o pipeline deve buscar na base de dados o `ExecutionSnapshot` com maior `nash_score` ordenado.
* **E** o status da Task deve ser ejetado como `COMPLETED_WITH_ROLLBACK`.
* **E** o campo `final_score` deve carregar exatamente `0.80` (resgatado do ciclo 1).

### Cenário F: Acionamento de Rollback por Estagnação de Epsilon ($\Delta W < \epsilon$)
* **Dado** que um pipeline completou o Ciclo 1 gravando um Snapshot com $W(x) = 0.85$.
* **E** o valor de corte Epsilon ($\epsilon$) do sistema é `0.02`.
* **Quando** o Ciclo 2 for executado e o novo cálculo do Motor de Nash retornar $W(x) = 0.86$.
* **Então** o cálculo de ganho marginal será $\Delta W = 0.01$.
* **E** como $0.01 < 0.02$, o orquestrador deve detectar estagnação e interromper o loop.
* **E** a Task deve ser ejetada com o status `COMPLETED_WITH_ROLLBACK`.
* **E** o `final_score` da Task deve resgatar e manter a melhor versão registrada (seja ela a do Ciclo 1 ou 2, a que for maior).

### Cenário G: Degradação Súbita ($\Delta W < 0$) com Rollback Imediato
* **Dado** que o pipeline completou o Ciclo 1 gravando um Snapshot de $W(x) = 0.82$.
* **E** não houve convergência (Target permanece $0.95$), autorizando o avanço ao Ciclo 2.
* **Quando** o Ciclo 2 é executado e o Motor de Nash retorna um $W(x) = 0.74$.
* **Então** o ganho marginal será $\Delta W = 0.74 - 0.82 = -0.08$ (estritamente negativo).
* **E** o orquestrador deve classificar o evento como **Degradação Sumária**, abortando a tarefa instantaneamente sem qualquer retentativa.
* **E** não deve existir um Ciclo 3 — o loop é encerrado no próprio Passo 6 do Ciclo 2.
* **E** a Task deve ser ejetada com o status `COMPLETED_WITH_ROLLBACK`.
* **E** o `final_text` e `final_score` devem conter exatamente os dados do Snapshot do Ciclo 1 ($0.82$), resgatados via `order_by('-nash_score').first()`.

### Cenário H: Schema Dinâmico do Pydantic Rejeita `axis_id` Alucinado
* **Dado** que um Perfil em execução possui os eixos com `valid_axis_ids = [1, 2]`.
* **E** o schema do corretor foi gerado via `build_dynamic_auditor_schema([1, 2])`.
* **Quando** o mock do Corretor retorna um JSON alucinando `axis_id=999` (ou omitindo o eixo `2`, devolvendo apenas `[1]`).
* **Então** o `AuditorResponseSchema.model_validate_json(...)` deve levantar `pydantic.ValidationError` (rejeição pelo `Literal` ou pelo `@field_validator('deductions')` de cobertura integral).
* **E** essa `ValidationError` é capturada pelo orquestrador e consumida como **1 Strike** no Guard-rail, sem propagar exceção ao Worker do Celery.
* **E** o Worker permanece vivo, registrando `current_step` indicando "Guard-rail (Tentativa X/3) — Erro de Schema".
* **E** nenhum `AuditorResult` corrompido deve ser persistido no banco de dados.

### Cenário I: Falha de Rede (`httpx.TimeoutException`) Consome Strike sem Quebrar o Worker
* **Dado** um pipeline em execução na Iteração 1.
* **Quando** a chamada `call_guardrail_agent` (ou `call_auditor_agent`) for mockada para levantar `httpx.TimeoutException`.
* **Então** o orquestrador deve capturar a exceção de I/O no bloco de resiliência e incrementar o contador de strikes da iteração em `1`.
* **E** o Worker do Celery **não** deve estourar (sem propagação da `TimeoutException` para o nível da task).
* **E** o `current_step` deve registrar explicitamente a falha de infraestrutura (ex: "Guard-rail (Tentativa 1/3) — Timeout de rede").
* **E** o campo `last_heartbeat_at` deve ser atualizado no momento da captura, mantendo a tarefa viva para o Ceifador.
* **Quando** a mesma falha de rede se repetir por 3 tentativas consecutivas.
* **Então** a Task deve assumir `status=ABORTED_GUARDRAIL_STRIKES`, com a justificativa registrando "infraestrutura" como causa dos 3 strikes.

---

## 4. Guia de Mocks e Fixtures (Snippets de Código)

Abaixo estão os padrões obrigatórios para estruturar testes com `unittest.mock` e Pydantic no LexiCraft.

### 4.1. Mockando o Retorno do Guard-rail
```python
# tests/mocks/agents.py
from unittest.mock import AsyncMock, patch
from apps.orchestrator.schemas import build_dynamic_auditor_schema, GuardrailResponseSchema, WriterResponseSchema

def get_mock_guardrail_approved() -> GuardrailResponseSchema:
    return GuardrailResponseSchema(
        reasoning="O texto cumpriu 100% das regras estipuladas e não possui alucinações.",
        is_approved=True,
        feedback_for_writer=None
    )

def get_mock_guardrail_rejected() -> GuardrailResponseSchema:
    return GuardrailResponseSchema(
        reasoning="O texto alucinou fatos sobre a tecnologia X.",
        is_approved=False,
        feedback_for_writer="Remova qualquer menção à tecnologia X imediatamente."
    )

def build_mock_auditor_payload(valid_axis_ids, deductions_by_axis, summary="Texto impecável."):
    """
    Monta um payload de corretor já validado pelo schema dinâmico para uso nos
    mocks do Tribunal. `deductions_by_axis` é um dict {axis_id: points_to_deduct}.
    """
    schema = build_dynamic_auditor_schema(valid_axis_ids)
    deductions = [
        {"axis_id": aid, "criterion_name": f"Eixo {aid}", "points_to_deduct": pts, "reasoning": "-"}
        for aid, pts in deductions_by_axis.items()
    ]
    return schema(summary=summary, deductions=deductions)
```

### 4.2. Patching do Módulo Assíncrono no Pytest
Exemplo de isolamento da função wrapper que chamaria a OpenAI:

```python
# tests/test_pipeline.py
import pytest
from unittest.mock import patch
from apps.orchestrator.tasks import run_optimization_pipeline

@pytest.mark.django_db(transaction=True)
@patch('apps.orchestrator.agents.guardrail.call_guardrail_agent')
@patch('apps.orchestrator.agents.writer.call_writer_agent')
@patch('apps.orchestrator.agents.auditor.call_auditor_agent')
def test_scenario_a_golden_path(mock_auditor, mock_writer, mock_guardrail, task_execution_factory):
    """
    Testa o fluxo perfeito BDD (Cenário A).
    """
    # 1. Configurar Task Execution (Fixture Factory)
    task = task_execution_factory(max_budget_usd=2.50)
    
    # 2. Configurar o Mock do Redator (retorna Dicionário no formato esperado do wrapper)
    mock_writer.return_value = {
        "parsed_payload": WriterResponseSchema(generated_text="Texto brilhante."),
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "total_tokens": 150
    }
    
    # 3. Configurar Mock do Guard-rail (Aprova de primeira)
    mock_guardrail.return_value = {
        "parsed_payload": get_mock_guardrail_approved(),
        "prompt_tokens": 80,
        "completion_tokens": 10,
        "total_tokens": 90
    }
    
    # 4. Configurar Mock do Tribunal (Retorna deduções zero)
    mock_auditor.return_value = {
        "parsed_payload": build_mock_auditor_payload(
            valid_axis_ids=[1, 2],
            deductions_by_axis={1: 0.0, 2: 0.0}
        ),
        "prompt_tokens": 200,
        "completion_tokens": 100,
        "total_tokens": 300
    }
    
    # 5. Execução (When)
    # Roda a função síncrona do Celery que internamente possui blocos asyncio.run()
    run_optimization_pipeline(task.id)
    
    # 6. Validação (Then)
    task.refresh_from_db()
    assert task.status == 'COMPLETED'
    assert task.snapshots.count() == 1
    assert task.final_score >= 0.95
```

---

## 5. Testes de Integração Web (Django Views, Constraints e HTMX)

Estes testes garantem que o "Monólito Majestoso" bloqueie a nível de banco de dados e roteamento comportamentos indevidos. Utilize o módulo `django.test.Client`.

### Cenário J: Proteção Matemática no Banco de Dados (CheckConstraints)
* **Dado** que um administrador cadastra um novo Eixo de Qualidade via Django ORM.
* **Quando** ele tentar salvar o `QualityAxis` configurando `weight=0.0` ou `weight=-1.5`.
* **Então** o banco PostgreSQL (e o SQLite na suíte de testes) deve levantar uma `IntegrityError` devido à `CheckConstraint` `check_axis_weight_positive`.
* **Quando** tentar salvar `base_score=0`, deve lançar erro via `check_axis_base_score_positive`.
* **E** **Quando** a rotina do worker tentar atualizar uma `TaskExecution` com `accumulated_cost_usd = -0.50` (falha bizarra de cálculo de tokens), o banco deve recusar imediatamente via `check_task_cost_non_negative`.

### Cenário K: Polling Dinâmico do Progresso com HTMX
* **Dado** uma Task de otimização em execução no background.
* **E** que o Frontend HTMX faça polling no endpoint de status (ex: `/tasks/<id>/status/`).
* **Quando** a View for requisitada recebendo o Header HTTP `HX-Request: true`.
* **Então** a View NÃO deve renderizar o layout completo (`base.html`).
* **E** deve retornar um *template parcial* (ex: `partials/task_progress.html`) indicando `task.current_step`.
* **Quando** a View for acessada pelo navegador padrão (sem o header HTMX).
* **Então** ela deve retornar um HTTP 400 Bad Request ou redirecionar o usuário, protegendo as parciais. 

```python
# tests/test_views.py
import pytest
from django.urls import reverse

@pytest.mark.django_db
def test_htmx_task_status_polling(client, task_execution_factory):
    """
    Garante que a resposta respeita o fluxo de fragmentos do HTMX.
    """
    task = task_execution_factory(status='RUNNING', current_step='Guard-rail (Tentativa 1/3)')
    url = reverse('task_status_partial', args=[task.id])
    
    # Simulando Header HTMX
    response = client.get(url, HTTP_HX_REQUEST='true')
    
    assert response.status_code == 200
    # Validações estruturais de fragmento HTML
    assert '<html' not in response.content.decode() 
    assert 'Guard-rail (Tentativa 1/3)' in response.content.decode()
    
    # Simulando Acesso sem Header (Direto pela URL)
    bad_response = client.get(url)
    assert bad_response.status_code in [400, 404, 302] # Conforme design escolhido
```
