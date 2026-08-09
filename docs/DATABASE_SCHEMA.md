# DATABASE_SCHEMA.md

## 1. Filosofia de Modelagem de Dados

O esquema de banco de dados do **LexiCraft** foi projetado seguindo as diretrizes do **Monólito Majestoso (Majestic Monolith)** no ecossistema Django + PostgreSQL. A modelagem garante alta integridade matemática, flexibilidade de configuração e otimização para cálculos analíticos de recuperação rápida.

* **Uso Estratégico do `JSONField`:**
  O sistema gerencia payloads dinâmicos retornados por LLMs. Para evitar a complexidade relacional de criar uma tabela para cada infração avaliada ou para notas individualizadas por critério, as avaliações validadas pelo `Pydantic` são diretamente ejetadas em campos `JSONField` nativos do PostgreSQL (campos `normalized_scores` e `deductions_payload`). Isso garante leitura em $O(1)$ pelo Motor Matemático.
* **Rastreabilidade e Versionamento (TimeStamped):**
  Todos os modelos derivam de um mixin base (`TimeStampedModel`) que injeta automaticamente `created_at` e `updated_at`. A Execução explicita dois marcadores temporais próprios do ciclo de execução: `started_at`, o *timestamp* exato da transição `PENDING -> RUNNING`, e `last_heartbeat_at`, o último sinal de vida emitido pelo Worker. O campo `started_at` é a única fonte de verdade utilizada pelo Celery para calcular o tempo total em andamento e disparar o disjuntor de Teto de Tempo ($T_{max}$); o `created_at` mede apenas o instante de enfileiramento e jamais entra no cálculo do teto, preservando o usuário de ser punido pelo tempo de fila do *broker*. O `last_heartbeat_at` sustenta o *Garbage Collector* de tarefas zumbis, que marca como `FAILED_TIMEOUT` toda execução `RUNNING` cujo sinal de vida esteja desatualizado.
* **Isolamento de Contagem de Tokens:**
  Os Large Language Models possuem precificação assimétrica (Tokens de Prompt geralmente são 3x a 5x mais baratos que Tokens de Completion). A separação explícita entre `accumulated_prompt_tokens` e `accumulated_completion_tokens` garante o cálculo de Isocusto preciso no nível do Worker.
* **Segurança Matemática no Banco:**
  Validações que protegem o motor `math_engine.py` começam no nível de restrição do SGBD (`CheckConstraint`), impedindo que pesos, bases numéricas ou custos sejam cadastrados com valores negativos, o que causaria colapso no Produto de Nash.

---

## 2. Definição dos Enums e TextChoices

Os Enums representam o ciclo de vida da orquestração e os perfis de atuação dos agentes. Eles devem residir no escopo global ou em um arquivo comum de utilitários (ex: `apps/core/choices.py`).

```python
from django.db import models
from django.utils.translation import gettext_lazy as _

class TaskStatus(models.TextChoices):
    PENDING = 'PENDING', _('Pendente')
    RUNNING = 'RUNNING', _('Em Execução')
    COMPLETED = 'COMPLETED', _('Concluído com Sucesso')
    COMPLETED_WITH_ROLLBACK = 'COMPLETED_WITH_ROLLBACK', _('Concluído com Rollback (Melhor Snapshot)')
    ABORTED_GUARDRAIL_STRIKES = 'ABORTED_GUARDRAIL_STRIKES', _('Abortado - Falha Crítica Guard-rail (3 Strikes)')
    FAILED_BUDGET_EXCEEDED = 'FAILED_BUDGET_EXCEEDED', _('Falha - Orçamento Excedido')
    FAILED_TIMEOUT = 'FAILED_TIMEOUT', _('Falha - Tempo Limite Excedido')
    FAILED_NO_SNAPSHOTS = 'FAILED_NO_SNAPSHOTS', _('Falha - Estagnado sem Snapshots')

class PromptRole(models.TextChoices):
    WRITER = 'WRITER', _('Agente Redator')
    GUARDRAIL = 'GUARDRAIL', _('Agente Guard-rail (Fidelidade)')
    AUDITOR = 'AUDITOR', _('Corretor Base (Tribunal)')

class AuditorType(models.TextChoices):
    CORRETOR_1 = 'CORRETOR_1', _('Corretor Paralelo 1')
    CORRETOR_2 = 'CORRETOR_2', _('Corretor Paralelo 2')
    DESEMPATE = 'DESEMPATE', _('Corretor de Desempate (3º)')
```

> **Modelos de LLM NÃO são hardcoded:** Diferente dos enums acima, o catálogo de
> modelos do provedor **OpenCode Go** não é um `TextChoices` estático — novos
> modelos entram e saem com frequência (inclusive depreciações). A lista é
> consultada em *runtime* a partir do endpoint público `https://opencode.ai/zen/go/v1/models`,
> que retorna todos os modelos disponíveis e seus metadados (IDs, custo por 1M de
> tokens de input/output, e datas de depreciação). O `ProfileConfig` grava o
> `model_name` como um `CharField` cujas *choices* são populadas dinamicamente por
> esse endpoint, garantindo que novos modelos sejam selecionáveis sem alteração de
> código. O modelo padrão (fallback) é o `deepseek-v4-flash`.

---

## 3. Código-Fonte dos Modelos (`models.py`)

### 3.1. Core Base Model (`apps/core/models.py`)

```python
from django.db import models

class TimeStampedModel(models.Model):
    """Modelo abstrato para herança de rastreabilidade."""
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
```

### 3.2. App Profiles (`apps/profiles/models.py`)

```python
from django.db import models
from django.core.validators import MinValueValidator
from apps.core.models import TimeStampedModel
from apps.core.choices import PromptRole

class ProfileConfig(TimeStampedModel):
    name = models.CharField(max_length=255, unique=True, verbose_name="Nome do Perfil")
    is_active = models.BooleanField(default=True, db_index=True)
    description = models.TextField(blank=True, null=True)
    
    # Modelo de LLM (OpenCode Go) utilizado por este Perfil.
    # As choices são populadas dinamicamente via https://opencode.ai/zen/go/v1/models
    # (ver service apps/orchestrator/services/model_catalog.py). Nada é hardcoded.
    model_name = models.CharField(
        max_length=100,
        default="deepseek-v4-flash",
        help_text="ID do modelo no catálogo OpenCode Go (fallback: deepseek-v4-flash)."
    )
    
    # Tetos padrão recomendados (Customizáveis por instância)
    default_max_iterations = models.PositiveSmallIntegerField(default=3)
    default_max_budget_usd = models.DecimalField(max_digits=6, decimal_places=4, default=2.50)
    default_max_time_seconds = models.PositiveIntegerField(
        default=300, 
        help_text="Tempo máximo de execução em segundos (T_max)"
    )

    class Meta:
        verbose_name = "Perfil de Geração"
        verbose_name_plural = "Perfis de Geração"

    def __str__(self) -> str:
        return self.name

class QualityAxis(TimeStampedModel):
    profile = models.ForeignKey(ProfileConfig, on_delete=models.CASCADE, related_name='axes')
    name = models.CharField(max_length=150, verbose_name="Critério/Eixo")
    weight = models.FloatField(
        default=1.0, 
        validators=[MinValueValidator(0.01)],
        help_text="Peso nominal. Será normalizado automaticamente (sum w_i = 1.0) no cálculo."
    )
    base_score = models.FloatField(
        default=100.0,
        validators=[MinValueValidator(1.0)],
        help_text="Pontuação total do critério antes das deduções."
    )
    deduction_rules = models.TextField(
        help_text="Subprompt injetado para o Corretor detalhando as regras de penalização."
    )

    class Meta:
        verbose_name = "Eixo de Qualidade"
        verbose_name_plural = "Eixos de Qualidade"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(weight__gt=0),
                name='check_axis_weight_positive'
            ),
            models.CheckConstraint(
                condition=models.Q(base_score__gt=0),
                name='check_axis_base_score_positive'
            )
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.profile.name})"

class SystemPrompt(TimeStampedModel):
    profile = models.ForeignKey(ProfileConfig, on_delete=models.CASCADE, related_name='prompts')
    role_type = models.CharField(max_length=50, choices=PromptRole.choices)
    content = models.TextField(help_text="Diretriz de sistema principal do Agente.")

    class Meta:
        verbose_name = "Prompt do Sistema"
        verbose_name_plural = "Prompts do Sistema"
        constraints = [
            models.UniqueConstraint(
                fields=['profile', 'role_type'], 
                name='unique_role_per_profile'
            )
        ]

    def __str__(self) -> str:
        return f"{self.get_role_type_display()} - {self.profile.name}"
```

### 3.3. App Orchestrator (`apps/orchestrator/models.py`)

```python
from django.db import models
from django.conf import settings
from apps.core.models import TimeStampedModel
from apps.core.choices import TaskStatus, AuditorType
from apps.profiles.models import ProfileConfig

class TaskExecution(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='lexicraft_tasks'
    )
    profile = models.ForeignKey(
        ProfileConfig, 
        on_delete=models.PROTECT, 
        related_name='executions'
    )
    status = models.CharField(max_length=50, choices=TaskStatus.choices, default=TaskStatus.PENDING)
    
# Entradas e Progresso
    original_prompt = models.TextField(help_text="Mensagem inicial do usuário")
    current_iteration = models.PositiveSmallIntegerField(default=1)
    current_step = models.CharField(max_length=255, blank=True, null=True, help_text="Progresso descritivo para HTMX")
    started_at = models.DateTimeField(
        blank=True, null=True, 
        help_text="Timestamp exato em que a task mudou de PENDING para RUNNING."
    )
    last_heartbeat_at = models.DateTimeField(
        blank=True, null=True, 
        help_text="Último sinal de vida do Worker. Atualizado a cada transição de step."
    )
    
    # Limites (Teto de Recursos copiado do Perfil no momento da criação)
    max_iterations = models.PositiveSmallIntegerField(default=3)
    max_budget_usd = models.DecimalField(max_digits=8, decimal_places=4)
    max_time_seconds = models.PositiveIntegerField(help_text="Tempo limite copiado do perfil no momento da criação")
    
    # Consumo de Isocusto (Tokens e Moeda)
    accumulated_prompt_tokens = models.PositiveIntegerField(default=0)
    accumulated_completion_tokens = models.PositiveIntegerField(default=0)
    accumulated_cost_usd = models.DecimalField(max_digits=10, decimal_places=6, default=0.0)
    
    # Resultado Final (Após Sucesso ou Rollback)
    final_text = models.TextField(blank=True, null=True)
    final_score = models.FloatField(blank=True, null=True, help_text="Pontuação Global W(x) atingida")

    class Meta:
        verbose_name = "Execução de Tarefa"
        verbose_name_plural = "Execuções de Tarefa"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(accumulated_cost_usd__gte=0.0),
                name='check_task_cost_non_negative'
            )
        ]

    def __str__(self) -> str:
        return f"Task #{self.pk} - {self.user.username} ({self.status})"

class ExecutionSnapshot(TimeStampedModel):
    task_execution = models.ForeignKey(
        TaskExecution, 
        on_delete=models.CASCADE, 
        related_name='snapshots'
    )
    iteration_number = models.PositiveSmallIntegerField()
    generated_text = models.TextField()
    
    # O produto final W(x) do Motor de Nash
    nash_score = models.FloatField(help_text="Score Global consolidado [0.01, 1.0]")
    
    # Dict das notas rigorosas S_i por critério: {"axis_id": 0.85, ...}
    normalized_scores = models.JSONField(default=dict)
    
    # Custo isolado desse ciclo exato para métricas marginais
    cycle_cost_usd = models.DecimalField(max_digits=8, decimal_places=6, default=0.0)

    class Meta:
        verbose_name = "Snapshot de Iteração"
        verbose_name_plural = "Snapshots de Iteração"
        indexes = [
            # CRÍTICO: Indexação para a query de Rollback (order_by('-nash_score'))
            models.Index(fields=['task_execution', '-nash_score'], name='idx_rollback_optim')
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['task_execution', 'iteration_number'], 
                name='unique_iteration_per_task'
            )
        ]

    def __str__(self) -> str:
        return f"Snapshot Iteração {self.iteration_number} (W={self.nash_score:.4f})"

class AuditorResult(TimeStampedModel):
    snapshot = models.ForeignKey(
        ExecutionSnapshot, 
        on_delete=models.CASCADE, 
        related_name='auditor_results'
    )
    auditor_type = models.CharField(max_length=50, choices=AuditorType.choices)
    
    # Serialização validada do `AuditorResponseSchema` (Pydantic)
    deductions_payload = models.JSONField(
        help_text="Estrutura Pydantic com justificativas e deduções brutas do Corretor."
    )

    class Meta:
        verbose_name = "Resultado do Corretor"
        verbose_name_plural = "Resultados dos Corretores"
        constraints = [
            models.UniqueConstraint(
                fields=['snapshot', 'auditor_type'], 
                name='unique_auditor_per_snapshot'
            )
        ]

    def __str__(self) -> str:
        return f"{self.get_auditor_type_display()} - Snapshot #{self.snapshot.pk}"
```

---

## 4. Constraints e Índices de Otimização (Meta)

O ORM foi configurado com os seguintes reforços a nível de PostgreSQL, presentes nos blocos `class Meta`:

### 4.1 Índices Compostos (B-Tree)
- `idx_rollback_optim` (`task_execution`, `-nash_score`): Este índice permite que o algoritmo de *Rollback*, acionado nas paradas por estagnação ($\Delta W < \epsilon$), degradação sumária ($\Delta W < 0$) ou estouro de teto, recupere o `best_snapshot` em tempo sub-milissegundo sem full-table scan. O banco mapeia a `task_execution` e já tem o `nash_score` ordenado de forma decrescente na folha do índice.

### 4.2 Restrições de Integridade Específicas (`CheckConstraint`)
- `check_axis_weight_positive`: O peso de um critério ($w_i$) nunca pode ser nulo ou $\le 0$. A matemática da normalização de pesos depende estritamente de valores $> 0$ para montar proporções.
- `check_axis_base_score_positive`: A nota base ($B_i$) precisa ser $> 0$. Evita a divisão por zero (`ZeroDivisionError`) na fórmula $S_i = \max(S_{min}, \frac{\text{Bruta}_i}{B_i})$.
- `check_task_cost_non_negative`: Impede inconsistências financeiras onde retornos imprecisos de APIs de LLMs gerem reduções do *budget consumido* (`accumulated_cost_usd >= 0`).

---

## 5. Boas Práticas para o Django Admin

Para atender o requisito da Especificação Mestra de garantir uma experiência *out-of-the-box* pré-configurada e totalmente customizável para o administrador, o registro da aplicação `profiles` deve seguir o padrão de interface aninhada (Inline) no Django Admin.

```python
# apps/profiles/admin.py
from django.contrib import admin
from .models import ProfileConfig, QualityAxis, SystemPrompt

class QualityAxisInline(admin.TabularInline):
    model = QualityAxis
    extra = 1
    fields = ('name', 'weight', 'base_score', 'deduction_rules')

class SystemPromptInline(admin.StackedInline):
    model = SystemPrompt
    extra = 0
    fields = ('role_type', 'content')

@admin.register(ProfileConfig)
class ProfileConfigAdmin(admin.ModelAdmin):
    list_display = ('name', 'model_name', 'is_active', 'default_max_iterations', 'default_max_budget_usd', 'default_max_time_seconds')
    list_filter = ('is_active', 'model_name')
    search_fields = ('name', 'description')
    inlines = [QualityAxisInline, SystemPromptInline]
    
    fieldsets = (
        (None, {
            'fields': ('name', 'model_name', 'is_active', 'description')
        }),
        ('Limites Globais (Default)', {
            'fields': ('default_max_iterations', 'default_max_budget_usd', 'default_max_time_seconds')
        })
    )
```

> O campo `model_name` é renderizado como *dropdown* cujas opções são carregadas
> dinamicamente do endpoint `https://opencode.ai/zen/go/v1/models` (via o service
> `apps/orchestrator/services/model_catalog.py`), e não de uma lista fixa de código.

Essa abordagem assegura que, em uma única tela de gestão, o administrador do sistema possa balancear os pesos geométricos ($w_i$), editar as bases de pontos, refinar as rubricas e injetar os comportamentos sistêmicos (System Prompts) do Guard-rail, Redator e Corretores para cada *Profile*.
