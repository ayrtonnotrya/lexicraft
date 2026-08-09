"""
Orquestrador Celery — o coração agêntico do LexiCraft.

Executa o loop fechado de otimização textual:
    Redator -> Guard-rail (3 Strikes) -> Tribunal Paralelo -> Math Engine.

Fonte da verdade: docs/AGENTS.md (Sessão 5) e docs/ARCHITECTURE.md.

A cada iteração, um "pass completo" (Redator + Guard-rail + Tribunal) compõe uma
tentativa. Falhas semânticas do Guard-rail, falhas de infraestrutura (rede) e
erros de schema do Tribunal consomem 1 Strike; 3 strikes consecutivos abortam a
task. Em caso de aprovação (tribunal concluído), os strikes são resetados.
"""
import asyncio
import json
import logging
from datetime import timedelta
from decimal import Decimal

from asgiref.sync import sync_to_async
from django.conf import settings
from django.utils import timezone

from config.celery import app as celery_app

from apps.core.choices import AuditorType, PromptRole, TaskStatus
from apps.core.utils import estimate_cost_usd
from apps.orchestrator.models import AuditorResult, ExecutionSnapshot, TaskExecution
from apps.orchestrator.services.math_engine import (
    calculate_delta_w,
    calculate_nash_bargaining,
    evaluate_tribunal_divergence,
)

from .agents import auditor as auditor_agent
from .agents import guardrail as guardrail_agent
from .agents import writer as writer_agent

logger = logging.getLogger(__name__)

# Limiar de divergência que aciona o 3º Corretor de Desempate (10%).
DIVERGENCE_THRESHOLD = 0.10
MAX_GUARDRAIL_ATTEMPTS = 3


def _now() -> object:
    return timezone.now()


# Conjunto de status que representam um encerramento definitivo da task.
# Qualquer função que grave um status terminal DEVE checar este conjunto antes
# de persistir, evitando sobrescrever uma decisão já consolidada por race
# condition (ex.: Ceifador marcando FAILED_TIMEOUT enquanto o Worker finalize).
TERMINAL_STATUSES = frozenset({
    TaskStatus.COMPLETED,
    TaskStatus.COMPLETED_WITH_ROLLBACK,
    TaskStatus.ABORTED_GUARDRAIL_STRIKES,
    TaskStatus.FAILED_BUDGET_EXCEEDED,
    TaskStatus.FAILED_TIMEOUT,
    TaskStatus.FAILED_NO_SNAPSHOTS,
    TaskStatus.CANCELLED,
})


def _is_terminal(task: TaskExecution) -> bool:
    """True se a task já atingiu um encerramento definitivo."""
    return task.status in TERMINAL_STATUSES


def _refresh_and_check_cancelled(task: TaskExecution) -> bool:
    """Relê a task do banco e verifica se o usuário pediu cancelamento.

    Cancelamento cooperativo: a view de cancelamento marca `status=CANCELLED`
    no banco; o Worker, entre passos do loop, relê e aborta gracefully,
    preservando o melhor snapshot gravado até ali.

    Retorna True se a task foi cancelada (caller deve `return` imediatamente).
    """
    task.refresh_from_db(fields=['status'])
    return task.status == TaskStatus.CANCELLED


def _handle_cancellation(task: TaskExecution) -> None:
    """Consolida o cancelamento: preserva melhor snapshot e finaliza step."""
    best_snapshot = task.snapshots.order_by('-nash_score').first()
    if best_snapshot:
        task.final_text = best_snapshot.generated_text
        task.final_score = best_snapshot.nash_score
    task.current_step = "Cancelado pelo usuário."
    # O status CANCELLED já foi setado pela view; apenas persistimos finais.
    task.save(update_fields=['final_text', 'final_score', 'current_step', 'updated_at'])


def _set_step(task: TaskExecution, step: str, save: bool = True) -> None:
    """Atualiza o progresso descritivo e o heartbeat do Worker."""
    task.current_step = step
    task.last_heartbeat_at = _now()
    if save:
        task.save(update_fields=['current_step', 'last_heartbeat_at', 'updated_at'])


def _accumulate(task: TaskExecution, prompt_tokens: int, completion_tokens: int) -> Decimal:
    """Acumula tokens e custo em USD na task, mantendo o heartbeat vivo."""
    task.accumulated_prompt_tokens += prompt_tokens
    task.accumulated_completion_tokens += completion_tokens
    cost = estimate_cost_usd(prompt_tokens, completion_tokens)
    task.accumulated_cost_usd = Decimal(task.accumulated_cost_usd) + cost
    task.last_heartbeat_at = _now()
    task.save(update_fields=[
        'accumulated_prompt_tokens',
        'accumulated_completion_tokens',
        'accumulated_cost_usd',
        'last_heartbeat_at',
        'updated_at',
    ])
    return cost


def _rollback(task: TaskExecution, status: str = TaskStatus.COMPLETED_WITH_ROLLBACK) -> None:
    """Recupera o melhor Snapshot histórico e ejeta a task com Rollback.

    Guarda de transição: NUNCA sobrescreve um status terminal já consolidado
    (COMPLETED, *_ROLLBACK, ABORTED_*, FAILED_*). Evita que o Ceifador, uma
    retentativa tardia ou um poll HTTP regrave um estado finalizado,
    sobrescrevendo a decisão definitiva do Worker (race condition).
    """
    if _is_terminal(task):
        return

    best_snapshot = task.snapshots.order_by('-nash_score').first()
    if best_snapshot:
        task.final_text = best_snapshot.generated_text
        task.final_score = best_snapshot.nash_score
        task.status = status
    else:
        task.status = TaskStatus.FAILED_NO_SNAPSHOTS
    task.save(update_fields=['final_text', 'final_score', 'status', 'updated_at'])


def _finalize_completed(task: TaskExecution, snapshot: ExecutionSnapshot) -> None:
    # Fence: não sobrescreve estado terminal previamente consolidado.
    if _is_terminal(task):
        return
    task.final_text = snapshot.generated_text
    task.final_score = snapshot.nash_score
    task.status = TaskStatus.COMPLETED
    task.current_step = "Concluído com sucesso (convergência atingida)."
    task.save(update_fields=['final_text', 'final_score', 'status', 'current_step', 'updated_at'])


async def _call_writer(task, system_prompt, original_prompt, model, previous_text, violations_report):
    result = await writer_agent.call_writer_agent(
        system_prompt=system_prompt,
        original_prompt=original_prompt,
        model=model,
        previous_text=previous_text,
        violations_report=violations_report,
    )
    return result['parsed_payload'], result['prompt_tokens'], result['completion_tokens']


async def _call_guardrail(task, system_prompt, original_prompt, generated_text, model):
    result = await guardrail_agent.call_guardrail_agent(
        system_prompt=system_prompt,
        original_prompt=original_prompt,
        generated_text=generated_text,
        model=model,
    )
    return result['parsed_payload'], result['prompt_tokens'], result['completion_tokens']


def _extract_deductions(parsed_payload) -> dict:
    """Extrai {axis_id: points_to_deduct} de um payload validado do Corretor."""
    return {item.axis_id: item.points_to_deduct for item in parsed_payload.deductions}


async def _call_tribunal_auditor(task, system_prompt, text, valid_axis_ids, axes, model):
    result = await auditor_agent.call_auditor_agent(
        system_prompt=system_prompt,
        user_text=text,
        valid_axis_ids=valid_axis_ids,
        model=model,
        axes=axes,
    )
    return result['parsed_payload'], result['prompt_tokens'], result['completion_tokens']


async def _touch_heartbeat(task):
    """Bate o heartbeat do Worker sem bloquear o event loop do tribunal.

    O Tribunal Paralelo executa múltiplos LLM calls de longa duração dentro de
    um único `asyncio.run`. Sem atualização de `last_heartbeat_at` entre eles,
    o Ceifador de Zumbis (janela de 120s+) pode classificar uma task VIVA e
    lenta como zumbi e abortá-la falsamente (race condition). A atualização é
    delegada ao thread pool via `sync_to_async` para evitar o
    SynchronousOnlyOperation do Django em código async.
    """
    await sync_to_async(_set_step)(task, task.current_step)


def _run_tribunal(task, system_prompt, text, valid_axis_ids, axes, model, bases):
    """Executa o Tribunal Paralelo e o desempate condicional (3º Corretor).

    Todo o I/O assíncrono roda dentro de `asyncio.run`; o ORM é atualizado pelo
    chamador síncrono (evita SynchronousOnlyOperation do Django).

    Retorna:
        (mean_deductions, active_auditor_types, auditor_payloads,
         prompt_tokens_total, completion_tokens_total)
    """
    async def _run():
        await _touch_heartbeat(task)
        results = await asyncio.gather(
            _call_tribunal_auditor(task, system_prompt, text, valid_axis_ids, axes, model),
            _call_tribunal_auditor(task, system_prompt, text, valid_axis_ids, axes, model),
        )
        ded1 = _extract_deductions(results[0][0])
        ded2 = _extract_deductions(results[1][0])
        auditors = [results[0][0], results[1][0]]
        prompt_total = results[0][1] + results[1][1]
        completion_total = results[0][2] + results[1][2]

        if evaluate_tribunal_divergence(ded1, ded2, bases, threshold=DIVERGENCE_THRESHOLD):
            await _touch_heartbeat(task)
            third = await _call_tribunal_auditor(task, system_prompt, text, valid_axis_ids, axes, model)
            ded3 = _extract_deductions(third[0])
            auditors.append(third[0])
            prompt_total += third[1]
            completion_total += third[2]
        else:
            ded3 = None

        return ded1, ded2, ded3, auditors, prompt_total, completion_total

    ded1, ded2, ded3, auditors, prompt_total, completion_total = asyncio.run(_run())

    if ded3 is not None:
        mean = {aid: (ded1.get(aid, 0.0) + ded2.get(aid, 0.0) + ded3.get(aid, 0.0)) / 3.0 for aid in bases}
        active_types = [AuditorType.CORRETOR_1, AuditorType.CORRETOR_2, AuditorType.DESEMPATE]
    else:
        mean = {aid: (ded1.get(aid, 0.0) + ded2.get(aid, 0.0)) / 2.0 for aid in bases}
        active_types = [AuditorType.CORRETOR_1, AuditorType.CORRETOR_2]

    return mean, active_types, auditors, prompt_total, completion_total


def _time_budget_exceeded(task: TaskExecution) -> bool:
    if not task.started_at:
        return False
    elapsed = _now() - task.started_at
    return elapsed.total_seconds() >= task.max_time_seconds


def _build_violations_report(auditor_payloads, active_types) -> str:
    """Constrói um resumo JSON das infrações para o Redator na próxima iteração."""
    lines = []
    for auditor_type, payload in zip(active_types, auditor_payloads):
        deductions = [
            {"axis_id": d.axis_id, "points_to_deduct": d.points_to_deduct, "reasoning": d.reasoning}
            for d in payload.deductions
        ]
        lines.append({"auditor": auditor_type, "deductions": deductions})
    return json.dumps(lines, ensure_ascii=False)


@celery_app.task(bind=True, name='orchestrator.run_optimization_pipeline')
def run_optimization_pipeline(self, task_execution_id: int) -> None:
    """Task principal: orquestra o loop agêntico de otimização textual."""
    task_execution = TaskExecution.objects.select_related('profile').get(pk=task_execution_id)
    profile = task_execution.profile

    if task_execution.status == TaskStatus.PENDING:
        task_execution.status = TaskStatus.RUNNING
        task_execution.started_at = _now()
        task_execution.last_heartbeat_at = _now()
        task_execution.save(update_fields=['status', 'started_at', 'last_heartbeat_at', 'updated_at'])

    axes = list(profile.axes.all())
    if not axes:
        _rollback(task_execution, TaskStatus.FAILED_NO_SNAPSHOTS)
        return

    axes_spec = [
        {
            'id': ax.id,
            'name': ax.name,
            'base_score': ax.base_score,
            'weight': ax.weight,
            'deduction_rules': ax.deduction_rules,
        }
        for ax in axes
    ]
    valid_axis_ids = [ax['id'] for ax in axes_spec]
    bases = {ax['id']: ax['base_score'] for ax in axes_spec}

    prompts = {p.role_type: p.content for p in profile.prompts.all()}
    writer_prompt = prompts.get(PromptRole.WRITER, 'Você é um redator profissional.')
    guardrail_prompt = prompts.get(PromptRole.GUARDRAIL, 'Audite fidelidade e escopo.')
    auditor_prompt = prompts.get(PromptRole.AUDITOR, 'Você é um corretor rigoroso.')

    model = task_execution.model_name or profile.model_name or settings.DEFAULT_MODEL_NAME
    target = float(settings.NASH_TARGET_SCORE)

    previous_score: float | None = None
    previous_text: str | None = None
    violations_report: str | None = None

    max_iterations = task_execution.max_iterations or settings.MAX_ITERATIONS_PER_TASK

    for iteration in range(1, max_iterations + 1):
        # Cancelamento cooperativo: checa antes de iniciar nova iteração.
        if _refresh_and_check_cancelled(task_execution):
            _handle_cancellation(task_execution)
            return

        task_execution.current_iteration = iteration
        task_execution.save(update_fields=['current_iteration', 'updated_at'])

        # ------------------------------------------------------------------
        # Passos 1-3 (combinados sob a Regra dos 3 Strikes): Redator + Guard-rail
        # + Tribunal. Cada tentativa é um "pass completo".
        # ------------------------------------------------------------------
        strikes = 0
        retry_feedback: str | None = None
        generated_text: str | None = None
        mean_deductions = None
        active_types = None
        auditor_payloads = None

        for attempt in range(1, MAX_GUARDRAIL_ATTEMPTS + 1):
            # Cancelamento cooperativo: checa antes de cada tentativa.
            if _refresh_and_check_cancelled(task_execution):
                _handle_cancellation(task_execution)
                return

            _set_step(task_execution, f"Executando Redator (Iteração {iteration}, Tentativa {attempt}/3)")

            try:
                # 1. Redator (falha de rede/schema/contrato = Strike, AGENTS.md 5.B).
                # Na 2ª/3ª tentativa da MESMA iteração, devolve ao Redator o
                # feedback acumulado do Guard-rail para ele corrigir o erro
                # (fonte: AGENTS.md 5.B — "devolve o feedback do Guard-rail ao
                # Redator para retentativa"). O violations_report do tribunal
                # continua sendo o histórico da iteração ANTERIOR.
                writer_feedback = (
                    retry_feedback
                    if attempt > 1
                    else (violations_report if iteration > 1 else None)
                )
                writer_payload, pt, ct = asyncio.run(_call_writer(
                    task_execution, writer_prompt, task_execution.original_prompt, model,
                    previous_text if iteration > 1 else None,
                    writer_feedback,
                ))
                _accumulate(task_execution, pt, ct)
                generated_text = writer_payload.generated_text.strip()

                # 2. Guard-rail (reprovação semântica, rede ou schema = Strike)
                _set_step(task_execution, f"Executando Guard-rail (Tentativa {attempt}/3)")
                guardrail_payload, pt, ct = asyncio.run(_call_guardrail(
                    task_execution, guardrail_prompt, task_execution.original_prompt, generated_text, model,
                ))
                _accumulate(task_execution, pt, ct)
            except Exception as exc:  # noqa: BLE001
                # Falha de infraestrutura (TimeoutException, ConnectError, 429/500,
                # BadRequestError 400 de temperatura/parâmetros incompatíveis).
                strikes += 1
                reason = type(exc).__name__
                retry_feedback = f"Erro de infraestrutura ({reason}): {exc}"
                _set_step(
                    task_execution,
                    f"Redator/Guard-rail (Tentativa {attempt}/3) — Timeout de rede / falha de infraestrutura ({reason})",
                )
                if strikes >= MAX_GUARDRAIL_ATTEMPTS:
                    _abort_guardrail(task_execution, "infraestrutura (rede)")
                    return
                continue

            if not guardrail_payload.is_approved:
                # Reprovação semântica: consome Strike e devolve feedback ao Redator.
                strikes += 1
                retry_feedback = guardrail_payload.feedback_for_writer or "Reescreva corrigindo as falhas apontadas."
                _set_step(task_execution, f"Guard-rail (Tentativa {attempt}/3) — Reprovado (Strike {strikes}/3)")
                if strikes >= MAX_GUARDRAIL_ATTEMPTS:
                    _abort_guardrail(task_execution, "fuga de escopo")
                    return
                continue

            # 3. Tribunal de Corretores Paralelos (+ Desempate condicional).
            #    Erros de schema (axis_id alucinado / critério omitido) e falhas
            #    de rede nos Corretores também consomem 1 Strike.
            # Cancelamento cooperativo: checa antes de iniciar o Tribunal (custoso).
            if _refresh_and_check_cancelled(task_execution):
                _handle_cancellation(task_execution)
                return
            _set_step(task_execution, f"Executando Tribunal de Corretores (Iteração {iteration})")
            try:
                mean_deductions, active_types, auditor_payloads, pt, ct = _run_tribunal(
                    task_execution, auditor_prompt, generated_text, valid_axis_ids, axes_spec, model, bases,
                )
                _accumulate(task_execution, pt, ct)
            except Exception as exc:  # noqa: BLE001
                strikes += 1
                reason = type(exc).__name__
                retry_feedback = f"Erro no Tribunal ({reason}): {exc}"
                _set_step(task_execution, f"Guard-rail (Tentativa {attempt}/3) — Erro de Schema/Infra ({reason})")
                if strikes >= MAX_GUARDRAIL_ATTEMPTS:
                    _abort_guardrail(task_execution, f"Erro de Schema/Infra no Tribunal ({reason})")
                    return
                continue

            # Pass completo aprovado: reseta os strikes para as próximas iterações.
            strikes = 0
            break

        if mean_deductions is None:
            # Nunca deveria acontecer após o loop; proteção contra fluxo inesperado.
            _abort_guardrail(task_execution, "falha inesperada no pipeline")
            return

        # ------------------------------------------------------------------
        # Passo 4: Motor Matemático (Nash)
        # ------------------------------------------------------------------
        _set_step(task_execution, f"Calculando Nash (Iteração {iteration})")
        criteria = [
            {
                'axis_id': ax['id'],
                'base_score': ax['base_score'],
                'weight': ax['weight'],
                'deductions': mean_deductions[ax['id']],
            }
            for ax in axes_spec
        ]
        nash = calculate_nash_bargaining(criteria)
        w_current = nash['nash_score']
        cycle_cost = Decimal(task_execution.accumulated_cost_usd)

        # ------------------------------------------------------------------
        # Passo 5: Gravação de Snapshot
        # ------------------------------------------------------------------
        snapshot = ExecutionSnapshot.objects.create(
            task_execution=task_execution,
            iteration_number=iteration,
            generated_text=generated_text,
            nash_score=w_current,
            normalized_scores=nash['normalized_scores'],
            cycle_cost_usd=cycle_cost,
        )
        for auditor_type, payload in zip(active_types, auditor_payloads):
            AuditorResult.objects.create(
                snapshot=snapshot,
                auditor_type=auditor_type,
                deductions_payload=payload.model_dump(),
            )

        # ------------------------------------------------------------------
        # Passo 6: Avaliação das Condições de Parada
        # ------------------------------------------------------------------
        delta_w = None
        if previous_score is not None:
            delta_w = calculate_delta_w(w_current, previous_score)

        # 1. Convergência (Sucesso).
        if w_current >= target:
            _finalize_completed(task_execution, snapshot)
            return

        # 2. Estouro de Isocusto (C_max).
        if Decimal(task_execution.accumulated_cost_usd) >= task_execution.max_budget_usd:
            _set_step(task_execution, "Orçamento excedido (C_max). Executando Rollback.")
            _rollback(task_execution)
            return

        # 3. Estouro de Tempo (T_max).
        if _time_budget_exceeded(task_execution):
            _set_step(task_execution, "Tempo limite excedido (T_max). Executando Rollback.")
            _rollback(task_execution)
            return

        # 4. Limite de Ciclos (N_max): esgota o número de tentativas configurado,
        #    mantendo a melhor versão (Rollback) caso a nota não tenha convergido.
        if iteration >= max_iterations:
            if delta_w is not None:
                _set_step(task_execution, f"Limite de iterações atingido (N_max). ΔW={delta_w}. Executando Rollback.")
            else:
                _set_step(task_execution, "Limite de iterações atingido (N_max). Executando Rollback.")
            _rollback(task_execution)
            return
        if iteration >= max_iterations:
            _set_step(task_execution, "Limite de iterações atingido (N_max). Executando Rollback.")
            _rollback(task_execution)
            return

        # Prepara a próxima iteração.
        previous_score = w_current
        previous_text = generated_text
        violations_report = _build_violations_report(auditor_payloads, active_types)

    # Fluxo de segurança: nunca deve chegar aqui sem encerramento.
    _rollback(task_execution)


def _abort_guardrail(task: TaskExecution, reason: str) -> None:
    """Registra o abortamento por 3 strikes consecutivos e encerra a task.

    Preserva o melhor Snapshot já gravado (se houver) em `final_text`/
    `final_score`, de modo que o histórico produzido nas iterações anteriores
    ao aborto não se perca na UI (ex.: aborto na iteração 2 deve manter o
    resultado da iteração 1 visível).
    """
    # Fence: não sobrescreve estado terminal previamente consolidado
    # (ex.: Ceifador já pode ter marcado FAILED_TIMEOUT em race).
    if _is_terminal(task):
        return
    best_snapshot = task.snapshots.order_by('-nash_score').first()
    if best_snapshot:
        task.final_text = best_snapshot.generated_text
        task.final_score = best_snapshot.nash_score
    _set_step(task, f"Abortado: 3 strikes consecutivos no Guard-rail ({reason}).")
    task.status = TaskStatus.ABORTED_GUARDRAIL_STRIKES
    task.save(update_fields=['final_text', 'final_score', 'status', 'updated_at'])


@celery_app.task(name='orchestrator.reap_zombie_tasks')
def reap_zombie_tasks() -> int:
    """Ceifador: marca como FAILED_TIMEOUT tasks RUNNING sem heartbeat recente.

    Fonte da verdade: docs/AGENTS.md (Sessão 5.E).

    A janela de tolerância é centralizada em
    `settings.REAPER_ZOMBIE_WINDOW_SECONDS` (padrão 240s) e deve cobrir o pior
    caso do Tribunal Paralelo com desempate (2-3 LLM calls de longa duração em
    sequência dentro de um único `asyncio.run`). Janelas menores (60s/120s)
    geravam abates falsos de tasks vivas e lentas (race condition).
    """
    threshold = _now() - timedelta(seconds=settings.REAPER_ZOMBIE_WINDOW_SECONDS)
    zombies = TaskExecution.objects.filter(status=TaskStatus.RUNNING, last_heartbeat_at__lt=threshold)
    count = 0
    for task in zombies:
        _rollback(task, status=TaskStatus.FAILED_TIMEOUT)
        count += 1
    return count
