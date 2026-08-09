"""
Views do Painel (Dashboard) — Django + HTMX.

Fonte da verdade: docs/AGENTS.md (Sessão 4.A).
Quando uma requisição é iniciada por HTMX (`HX-Request`), as views retornam
fragmentos parciais de `templates/partials/`; o acesso direto aos endpoints
parciais sem o header é bloqueado com 400.
"""
import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import models
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.orchestrator.models import TaskExecution
from apps.orchestrator.services.model_catalog import fetch_available_models
from apps.orchestrator.tasks import reap_zombie_tasks, run_optimization_pipeline
from apps.profiles.models import ProfileConfig

logger = logging.getLogger(__name__)


def _is_htmx(request: HttpRequest) -> bool:
    return request.headers.get('HX-Request') == 'true'


def _reap_zombies_synchronously() -> int:
    """Fallback HTTP do Ceifador de Zumbis (Sessão 5.E do AGENTS.md).

    Caso o Celery Beat não esteja no ar, cada carregamento da home varre
    tasks RUNNING sem heartbeat recente e as converte em FAILED_TIMEOUT,
    preservando o melhor Snapshot. Garante que o usuário sempre enxergue
    um encerramento explícito — jamais uma task congelada em RUNNING.
    """
    try:
        result = reap_zombie_tasks.apply()
        return result.result if result.successful() else 0
    except Exception:  # noqa: BLE001
        logger.warning("Fallback de reaper falhou", exc_info=True)
        return 0


@login_required
def dashboard_index(request: HttpRequest) -> HttpResponse:
    """Tela principal: lista perfis ativos e tasks recentes do usuário."""
    _reap_zombies_synchronously()
    profiles = ProfileConfig.objects.filter(is_active=True).order_by('name')
    tasks = TaskExecution.objects.filter(user=request.user).order_by('-created_at')[:20]
    models_catalog = fetch_available_models()
    if not models_catalog:
        models_catalog = [{"id": settings.DEFAULT_MODEL_NAME}]

    # Modelo padrão: escolha salva do usuário prevalece; sem escolha salva,
    # usa a fonte única de verdade settings.DEFAULT_MODEL_NAME
    # (="deepseek-v4-flash"), de modo que o dropdown a preselectiona.
    default_model = request.COOKIES.get('lexicraft_model', '') or settings.DEFAULT_MODEL_NAME

    return render(request, 'dashboard/index.html', {
        'profiles': profiles,
        'tasks': tasks,
        'models_catalog': models_catalog,
        'default_model': default_model,
    })


@login_required
def recent_tasks_partial(request: HttpRequest) -> HttpResponse:
    """Endpoint parcial HTMX — fragmento da lista de Execuções Recentes.

    Permite que a home atualize a lista por polling (5s) sem recarregar a
    página, de modo que uma task recém-criada apareça automaticamente.
    """
    if not _is_htmx(request):
        return HttpResponse(status=400)
    _reap_zombies_synchronously()
    tasks = TaskExecution.objects.filter(user=request.user).order_by('-created_at')[:20]
    return render(request, 'partials/recent_tasks.html', {'tasks': tasks})


@login_required
@require_POST
def start_task(request: HttpRequest) -> HttpResponse:
    """Cria uma TaskExecution e dispara a tarefa Celery assíncrona.

    Guarda contra duplo submit (duplo clique / reload de POST): se já existe
    uma task do mesmo usuário + perfil com o MESMO texto em estado não-terminal
    (RUNNING/PENDING) ou criada há menos de 30s, redireciona para ela em vez de
    duplicar. Previne desperdício de orçamento em execuções gêmeas.
    """
    profile_id = request.POST.get('profile_id')
    text = request.POST.get('original_prompt', '').strip()
    model = (request.POST.get('model') or '').strip()

    if not profile_id or not text:
        return JsonResponse({'error': 'Perfil e texto são obrigatórios.'}, status=400)

    profile = get_object_or_404(ProfileConfig, pk=profile_id, is_active=True)

    # Modelo desacoplado do perfil: usa o escolhido no dropdown, caindo para o
    # model_name do perfil apenas quando o form não enviar um modelo.
    if not model:
        model = profile.model_name or settings.DEFAULT_MODEL_NAME

    # Verifica task recentemente existente e equivalente (mesmo perfil + texto).
    recent_threshold = timezone.now() - timedelta(seconds=30)
    existing = (
        TaskExecution.objects
        .filter(
            user=request.user,
            profile_id=profile_id,
            original_prompt=text,
        )
        .filter(
            models.Q(status__in=['PENDING', 'RUNNING'])
            | models.Q(created_at__gte=recent_threshold)
        )
        .order_by('-created_at')
        .first()
    )
    if existing is not None:
        # Dedup calculado: reaproveita a task em curso em vez de bifurcar.
        return redirect('dashboard:task_detail', task_id=existing.id)

    task = TaskExecution.objects.create(
        user=request.user,
        profile=profile,
        original_prompt=text,
        status='PENDING',
        model_name=model,
        max_iterations=profile.default_max_iterations,
        max_budget_usd=profile.default_max_budget_usd,
        max_time_seconds=profile.default_max_time_seconds,
    )
    run_optimization_pipeline.delay(task.id)
    return redirect('dashboard:task_detail', task_id=task.id)


@login_required
def task_detail(request: HttpRequest, task_id: int) -> HttpResponse:
    """Página de detalhe da task com polling HTMX do progresso."""
    _reap_zombies_synchronously()
    task = get_object_or_404(TaskExecution, pk=task_id, user=request.user)
    is_stale = False
    if task.status == 'RUNNING' and task.last_heartbeat_at:
        is_stale = (timezone.now() - task.last_heartbeat_at).total_seconds() > 120
    axes_by_id = {ax.id: ax.name for ax in task.profile.axes.all()}
    return render(request, 'dashboard/task_detail.html', {
        'task': task, 'is_stale': is_stale, 'axes_by_id': axes_by_id,
    })


@login_required
def task_status_partial(request: HttpRequest, task_id: int) -> HttpResponse:
    """Endpoint parcial HTMX — renderiza apenas o fragmento de progresso."""
    _reap_zombies_synchronously()
    task = get_object_or_404(TaskExecution, pk=task_id, user=request.user)
    if not _is_htmx(request):
        return HttpResponse(status=400)

    # Flag de heartbeat obsoleto: sinaliza ao partial que o Worker pode ter
    # morrido (mesmo antes do Ceifador marcar formalmente FAILED_TIMEOUT).
    is_stale = False
    if task.status == 'RUNNING' and task.last_heartbeat_at:
        is_stale = (timezone.now() - task.last_heartbeat_at).total_seconds() > 120

    axes_by_id = {ax.id: ax.name for ax in task.profile.axes.all()}
    return render(request, 'partials/task_progress.html', {
        'task': task, 'is_stale': is_stale, 'axes_by_id': axes_by_id,
    })


@login_required
def snapshot_partial(request: HttpRequest, task_id: int, snapshot_id: int) -> HttpResponse:
    """Endpoint parcial HTMX — renderiza um card de snapshot."""
    task = get_object_or_404(TaskExecution, pk=task_id, user=request.user)
    snapshot = get_object_or_404(task.snapshots, pk=snapshot_id)
    if not _is_htmx(request):
        return HttpResponse(status=400)
    axes_by_id = {ax.id: ax.name for ax in task.profile.axes.all()}
    return render(request, 'partials/snapshot_card.html', {'snapshot': snapshot, 'axes_by_id': axes_by_id})


@login_required
@require_POST
def cancel_task(request: HttpRequest, task_id: int) -> HttpResponse:
    """Cancela uma task em curso (PENDING/RUNNING) via cancelamento cooperativo.

    Marca `status=CANCELLED` no banco. O Worker, que checa cancelamento entre
    passos do loop, relê este estado e aborta graceful no próximo ponto seguro,
    preservando o melhor snapshot já gravado.

    Segurança: só o dono pode cancelar; só tasks não-terminais são canceláveis.
    HTMX: responde com o partial atualizado (HX-Request) ou redirect 303.
    """
    task = get_object_or_404(TaskExecution, pk=task_id, user=request.user)
    cancellable_statuses = {'PENDING', 'RUNNING'}
    if task.status in cancellable_statuses:
        task.status = 'CANCELLED'
        task.save(update_fields=['status', 'updated_at'])
        logger.info("Task #%s cancelada pelo usuário %s", task_id, request.user.username)

    if _is_htmx(request):
        is_stale = False
        if task.status == 'RUNNING' and task.last_heartbeat_at:
            is_stale = (timezone.now() - task.last_heartbeat_at).total_seconds() > 120
        axes_by_id = {ax.id: ax.name for ax in task.profile.axes.all()}
        return render(request, 'partials/task_progress.html', {
            'task': task, 'is_stale': False, 'axes_by_id': axes_by_id,
        })
    return redirect('dashboard:task_detail', task_id=task_id)
