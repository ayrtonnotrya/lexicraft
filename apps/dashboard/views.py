"""
Views do Painel (Dashboard) — Django + HTMX.

Fonte da verdade: docs/AGENTS.md (Sessão 4.A).
Quando uma requisição é iniciada por HTMX (`HX-Request`), as views retornam
fragmentos parciais de `templates/partials/`; o acesso direto aos endpoints
parciais sem o header é bloqueado com 400.
"""
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.orchestrator.models import TaskExecution
from apps.orchestrator.tasks import run_optimization_pipeline
from apps.profiles.models import ProfileConfig


def _is_htmx(request: HttpRequest) -> bool:
    return request.headers.get('HX-Request') == 'true'


@login_required
def dashboard_index(request: HttpRequest) -> HttpResponse:
    """Tela principal: lista perfis ativos e tasks recentes do usuário."""
    profiles = ProfileConfig.objects.filter(is_active=True).order_by('name')
    tasks = TaskExecution.objects.filter(user=request.user).order_by('-created_at')[:20]
    return render(request, 'dashboard/index.html', {'profiles': profiles, 'tasks': tasks})


@login_required
@require_POST
def start_task(request: HttpRequest) -> HttpResponse:
    """Cria uma TaskExecution e dispara a tarefa Celery assíncrona."""
    profile_id = request.POST.get('profile_id')
    text = request.POST.get('original_prompt', '').strip()

    if not profile_id or not text:
        return JsonResponse({'error': 'Perfil e texto são obrigatórios.'}, status=400)

    profile = get_object_or_404(ProfileConfig, pk=profile_id, is_active=True)
    task = TaskExecution.objects.create(
        user=request.user,
        profile=profile,
        original_prompt=text,
        status='PENDING',
        max_iterations=profile.default_max_iterations,
        max_budget_usd=profile.default_max_budget_usd,
        max_time_seconds=profile.default_max_time_seconds,
    )
    run_optimization_pipeline.delay(task.id)
    return redirect('task_detail', task_id=task.id)


@login_required
def task_detail(request: HttpRequest, task_id: int) -> HttpResponse:
    """Página de detalhe da task com polling HTMX do progresso."""
    task = get_object_or_404(TaskExecution, pk=task_id, user=request.user)
    return render(request, 'dashboard/task_detail.html', {'task': task})


@login_required
def task_status_partial(request: HttpRequest, task_id: int) -> HttpResponse:
    """Endpoint parcial HTMX — renderiza apenas o fragmento de progresso."""
    task = get_object_or_404(TaskExecution, pk=task_id, user=request.user)
    if not _is_htmx(request):
        return HttpResponse(status=400)
    return render(request, 'partials/task_progress.html', {'task': task})


@login_required
def snapshot_partial(request: HttpRequest, task_id: int, snapshot_id: int) -> HttpResponse:
    """Endpoint parcial HTMX — renderiza um card de snapshot."""
    task = get_object_or_404(TaskExecution, pk=task_id, user=request.user)
    snapshot = get_object_or_404(task.snapshots, pk=snapshot_id)
    if not _is_htmx(request):
        return HttpResponse(status=400)
    return render(request, 'partials/snapshot_card.html', {'snapshot': snapshot})
