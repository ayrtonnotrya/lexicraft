# MATH_SPEC.md

## Especificação Formal Matemática e Algorítmica do LexiCraft

Este documento atua como a fonte da verdade para o motor de cálculos (`math_engine.py`) do LexiCraft. Ele detalha as equações determinísticas, limites numéricos, condições de contorno e vetores de teste necessários para o desenvolvimento orientado a testes (TDD) e auditoria de funcionamento.

---

### 1. Filosofia de Isolamento Matemático

O motor adota o princípio de **Desacoplamento Cognitivo/Matemático**:
* **A Inteligência Artificial (LLMs)** opera **exclusivamente no domínio semântico**. Sua única função matemática é classificar erros e extrair o número bruto de pontos a serem deduzidos em uma infração (através de um JSON com tipagem estrita). Modelos de linguagem sofrem de alucinação aritmética e não possuem previsibilidade geométrica confiável.
* **O Motor Python (`math_engine.py`)** opera **exclusivamente no domínio determinístico**. Ele assume 100% da responsabilidade por agregações, normalizações, desempates e cálculo contínuo. 

**Princípios do Motor:**
1. **Imutabilidade de Operações:** O cálculo rodado 100 vezes com as mesmas deduções gerará exatamente o mesmo resultado até a $6^{\text{a}}$ casa decimal.
2. **Tolerância a Falhas (Piso de Nash):** O sistema previne matematicamente o colapso por zero, garantindo que a falha catastrófica de um eixo não zere irreversivelmente toda a pontuação da iteração (impossibilitando análises comparativas marginais).

---

### 2. Definições Formais e Equações do Motor

O pipeline recebe um vetor de critérios configurados (eixos) com seus respectivos Pesos Nominais ($p_i$) e Pontuações Base ($B_i$).

#### 2.1. Normalização de Pesos do Perfil ($w_i$)
Para garantir a integridade da equação geométrica, os pesos nominais são convertidos em pesos proporcionais de soma exata $1.0$.

$$w_i = \frac{p_i}{\sum_{k=1}^{N} p_k} \quad \text{tal que} \quad \sum_{i=1}^{N} w_i = 1.0$$

#### 2.2. Cálculo da Nota Bruta por Critério ($\text{Bruta}_i$)
A nota bruta é a pontuação base deduzida da soma de todas as infrações apontadas pelo Tribunal para aquele critério $i$. O valor é limitado inferiormente em $0.0$ para evitar notas negativas.

$$\text{Bruta}_i = \max\left(0.0, B_i - \sum_{j=1}^{M} D_{i,j}\right)$$
*(Onde $D_{i,j}$ é a dedução consolidada da infração $j$ no critério $i$)*.

#### 2.3. Normalização Rígida no Intervalo $[S_{min}, 1.0]$ ($S_i$)
Para que o Score de Nash faça sentido, as notas brutas são convertidas para uma escala padronizada. 

$$S_i = \max\left(S_{min}, \min\left(1.0, \frac{\text{Bruta}_i}{B_i}\right)\right)$$

* **Tratamento de Borda ($S_{min}$):** É definido explicitamente o piso **$S_{min} = 0.01$**.
* **Justificativa Matemática:** Como a Barganha de Nash é uma produtória (multiplicação geométrica), uma nota $S_i = 0$ resultaria em $W(x) = 0$ independente do quão perfeitos fossem os demais eixos (Propriedade do Elemento Absorvente). O limite de $0.01$ preserva a proporcionalidade de penalização severa sem apagar a contribuição das outras variáveis.

#### 2.4. Barganha de Nash Assimétrica ($W(x)$)
A pontuação global da iteração é dada pelo produto geométrico ponderado de todos os eixos.

$$W(x) = \prod_{i=1}^{N} (S_i)^{w_i}$$

* **Nash vs Média Aritmética:** O LexiCraft utiliza a Barganha de Nash porque ela **penaliza assimetrias**. Se um texto tira $1.0$ (Perfeito) em Clareza e $0.2$ (Péssimo) em Gramática, a Média Aritmética seria $0.6$ (mascarando a falha inaceitável). A Barganha de Nash puxa a nota agressivamente para baixo ($\approx 0.447$), forçando a IA a otimizar o gargalo na próxima iteração para ganhar eficiência marginal.

---

### 3. Matemática do Tribunal de Corretores e Desempate

O julgamento paralelo é consolidado através de avaliação de variância. Sejam $D_{1, i}$ e $D_{2, i}$ a soma total de pontos deduzidos no critério $i$ pelos Corretores 1 e 2, respectivamente.

#### 3.1. Fórmula de Divergência Relativa
A divergência é calculada proporcionalmente à Pontuação Base do critério:

$$\text{Divergência}_i = \frac{|D_{1, i} - D_{2, i}|}{B_i}$$

#### 3.2. Gatilho de Desempate
* **Condição:** Se existir **pelo menos um** critério $i$ onde $\text{Divergência}_i > 0.10$ ($10\%$), o orquestrador invoca o 3º Corretor de Desempate. (Ex: Diferença de 11 pontos em um eixo com Base 100).

#### 3.3. Consolidação por Média
A dedução final atribuída ao critério $i$ que alimentará o cálculo do Nash é a média matemática estrita das avaliações do Tribunal:

$$D_{consolidada, i} = \frac{1}{K} \sum_{k=1}^{K} D_{k, i} \quad (K \in \{2, 3\})$$

---

### 4. Matemática das Condições de Parada e Orçamento

#### 4.1. Estagnação e Degradação Sumária Baseada em Épsilon ($\Delta W$)
O pipeline avalia o ganho marginal a cada novo ciclo antes de decidir continuar ou encerrar. Seja $\Delta W = W_t - W_{t-1}$ o delta entre a iteração corrente e a imediatamente anterior.

$$\Delta W = W_t - W_{t-1}$$

Três regimes de parada derivam desse delta:

1. **Ganho Nulo (Estagnação):** Se $0 \le \Delta W < \epsilon$ (Default $\epsilon = 0.02$), a otimização não agrega valor marginal suficiente. O loop é interrompido com **Rollback** para o melhor snapshot.
2. **Degradação Sumária ($\Delta W < 0$):** Se o ganho marginal for estritamente negativo, o texto **piorou** em relação ao ciclo anterior. Esta condição é tratada como estagnação severa e irrecuperável: o orquestrador aborta a tarefa **instantaneamente**, sem retentativa, aplicando **Rollback** imediato para o melhor snapshot histórico ($k^* = \arg\max W_k$). Não existe regime de "recuperação" após degradação — o loop é encerrado e a melhor versão observada é ejetada.
3. **Convergência:** $\Delta W \ge 0$ e $W_t \ge Target$ encerra com sucesso (`COMPLETED`), sem depender de épsilon.

O piso $S_{min}$ preserva a comparabilidade entre ciclos mesmo em colapsos parciais, garantindo que $\Delta W$ permaneça um sinal numéricamente estável (jamais $-\infty$) para a decisão de degradação.

#### 4.2. Isocusto (Equação de Consumo API)
Dado um custo tabelado por 1 Milhão ($10^6$) de tokens de *Prompt* ($P_{prompt}$) e de *Completion* ($P_{completion}$), o custo acumulado da tarefa ($C_{task}$) após $Calls$ chamadas de API é:

$$C_{task} = \sum_{c=1}^{Calls} \left( \frac{\text{PromptTokens}_c}{1000000} \cdot P_{prompt} + \frac{\text{CompletionTokens}_c}{1000000} \cdot P_{completion} \right)$$

#### 4.3. Teto de Tempo e Disjuntores de Recurso
O teto de tempo ($T_{max}$) é definido como a diferença entre o instante corrente e o início efetivo da execução:

$$T_{task} = \text{now}() - \text{started\_at}$$

O campo `started_at` é populado exatamente na transição `PENDING -> RUNNING` e é a **única** fonte de verdade para o teto de tempo. O `created_at` (instante de enfileiramento no *broker* do Celery) é deliberadamente excluído do cálculo, de modo que o tempo de fila nunca penalize o usuário — a contagem só corre a partir do momento em que o Worker efetivamente assume a tarefa.

* **Disjuntores Teto:** Se $C_{task} \ge C_{max}$, $T_{task} \ge T_{max}$ ou o número de ciclos atingir $N_{max}$, a rotina de interrupção imediata é acionada, executando **Rollback** para o melhor snapshot.

---

### 5. Algoritmo de Rollback da Melhor Versão

Caso a otimização atinja qualquer teto, estagnação marginal ($\Delta W < \epsilon$) ou degradação sumária ($\Delta W < 0$) antes do Alvo Global ($Target$), realiza-se o processo de salvamento da melhor versão histórica.

Seja $\mathbb{S}$ o conjunto de snapshots gravados e validados:
$$k^* = \arg\max_{k \in \{1 \dots N_{snapshots}\}} (W_k)$$

* **Tratamento de Borda ($N_{snapshots} = 0$):** Se a tarefa falhar durante o Loop 1, antes do primeiro snapshot, o status muda para `FAILED_NO_SNAPSHOTS`, abortando sem ejetar texto.

---

### 6. Código de Referência Completo (`math_engine.py`)

Abaixo a implementação canônica *Pure Python* rigorosa para validação e testes:

```python
import math
from typing import List, Dict, Any, TypedDict

class CriterionConfig(TypedDict):
    axis_id: int
    base_score: float
    weight: float
    deductions: float  # Dedução já consolidada pela média do tribunal

def calculate_nash_bargaining(
    criteria: List[CriterionConfig], 
    s_min: float = 0.01
) -> Dict[str, Any]:
    """
    Calcula a Normalização Rígida [0.01, 1.0] e a Barganha de Nash Assimétrica W(x).
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
        
        # 1. Normalização do peso (wi)
        w_i = item['weight'] / total_weight
        normalized_weights[axis_id] = w_i
        
        # 2. Cálculo da Nota Bruta
        raw_score = max(0.0, item['base_score'] - item['deductions'])
        raw_scores[axis_id] = raw_score
        
        # 3. Normalização Rígida Si no intervalo [s_min, 1.0]
        s_i = max(s_min, min(1.0, raw_score / item['base_score']))
        normalized_scores[axis_id] = s_i
        
        # 4. Acumulação Geométrica da Barganha de Nash
        nash_product *= math.pow(s_i, w_i)

    return {
        "nash_score": round(nash_product, 6),
        "normalized_scores": {k: round(v, 6) for k, v in normalized_scores.items()},
        "raw_scores": raw_scores,
        "normalized_weights": {k: round(v, 6) for k, v in normalized_weights.items()}
    }

def evaluate_tribunal_divergence(
    deductions_auditor_1: Dict[int, float], 
    deductions_auditor_2: Dict[int, float], 
    bases: Dict[int, float], 
    threshold: float = 0.10
) -> bool:
    """
    Avalia se existe divergência > threshold (10%) entre dois corretores
    em qualquer eixo avaliado. Retorna True se exigir um 3º Corretor.
    """
    for axis_id, base_score in bases.items():
        if base_score <= 0:
            continue
            
        d1 = deductions_auditor_1.get(axis_id, 0.0)
        d2 = deductions_auditor_2.get(axis_id, 0.0)
        
        divergence = abs(d1 - d2) / base_score
        if divergence > threshold:
            return True
            
    return False

def calculate_delta_w(w_current: float, w_previous: float) -> float:
    """Calcula o ganho marginal da iteração."""
    return round(w_current - w_previous, 6)
```

---

### 7. Vetores de Teste para TDD (Entrada vs Saída Esperada)

Os cenários abaixo devem ser obrigatoriamente replicados em `tests/test_math_engine.py`. Todas as aproximações estão truncadas na $6^{\text{a}}$ casa decimal.

#### Cenário 1: Pontuação Perfeita (Base Padrão)
* **Entradas:** 3 Eixos, Base = 100, Peso = 1. Deduções = `[0, 0, 0]`.
* **Motor Resultante:**
  * $w_i$: `[0.333333, 0.333333, 0.333333]`
  * $S_i$: `[1.000000, 1.000000, 1.000000]`
  * **$W(x)$:** `1.000000`

#### Cenário 2: Tratamento de Borda e Colapso Catastrófico ($S_{min}$)
* **Entradas:** Eixo 1 (Base=100, Peso=1, Dedução=0), Eixo 2 (Base=100, Peso=1, Dedução=150).
* **Motor Resultante:**
  * Eixo 1 Bruta: 100. $S_1$ = `1.000000`.
  * Eixo 2 Bruta: 0 (pois `100 - 150` limitado a `0`). $S_2$ = `0.010000`. (Aqui o $S_{min}$ atua).
  * $w_i$: `[0.5, 0.5]`.
  * **$W(x)$:** `0.100000` *(Resultado exato de $\sqrt{1.0 \times 0.01}$)*.

#### Cenário 3: Nash Assímetrico vs Média (Diferença de Penalidade)
* **Entradas:** Eixo 1 (Base=100, Peso=1, Dedução=10), Eixo 2 (Base=100, Peso=1, Dedução=80).
* **Motor Resultante:**
  * $S_1$ = `0.900000`
  * $S_2$ = `0.200000`
  * Média Aritmética Ingênua seria: `0.550000`
  * **Nash Calculado $W(x)$:** `0.424264` *(Penaliza a discrepância severa do Eixo 2)*.

#### Cenário 4: Pesos Diferentes e Distribuição
* **Entradas:**
  * Eixo 1: Peso = 2.0, Base = 100, Dedução = 10 ($S_1 = 0.90$)
  * Eixo 2: Peso = 1.0, Base = 100, Dedução = 20 ($S_2 = 0.80$)
* **Motor Resultante:**
  * Total de pesos = 3.0.
  * $w_1 = 2/3 \approx 0.666667$
  * $w_2 = 1/3 \approx 0.333333$
  * Fatores: $0.90^{0.666667} \times 0.80^{0.333333} = 0.932170 \times 0.928318$
  * **$W(x)$:** `0.865350`

#### Cenário 5: Avaliação do Tribunal de Corretores (Divergência)
* **Entradas:**
  * Corretor 1 deduz `10` pontos no Eixo 1.
  * Corretor 2 deduz `25` pontos no Eixo 1.
  * Base = `100`. Limiar ($\epsilon$) = `0.10`.
* **Cálculo da Divergência:**
  * $|10 - 25| = 15$.
  * Relativa: $15 / 100 = 0.15$.
* **Motor Resultante:**
  * $0.15 > 0.10 \implies$ **Retorna `True`** (Exige 3º Corretor obrigatório).
