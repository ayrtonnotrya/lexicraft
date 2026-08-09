"""Django Admin da app `orchestrator` — leitura e rastreabilidade das execuções."""
from django.contrib import admin

from .models import AuditorResult, ExecutionSnapshot, TaskExecution


class ExecutionSnapshotInline(admin.TabularInline):
    model = ExecutionSnapshot
    extra = 0
    readonly_fields = ('iteration_number', 'generated_text', 'nash_score', 'normalized_scores')


@admin.register(TaskExecution)
class TaskExecutionAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'user',
        'profile',
        'status',
        'current_iteration',
        'accumulated_cost_usd',
        'final_score',
        'created_at',
    )
    list_filter = ('status', 'profile')
    search_fields = ('original_prompt',)
    readonly_fields = (
        'user',
        'profile',
        'status',
        'current_iteration',
        'current_step',
        'started_at',
        'last_heartbeat_at',
        'accumulated_prompt_tokens',
        'accumulated_completion_tokens',
        'accumulated_cost_usd',
        'final_text',
        'final_score',
    )
    inlines = [ExecutionSnapshotInline]


@admin.register(ExecutionSnapshot)
class ExecutionSnapshotAdmin(admin.ModelAdmin):
    list_display = ('id', 'task_execution', 'iteration_number', 'nash_score', 'created_at')
    list_filter = ('task_execution',)


@admin.register(AuditorResult)
class AuditorResultAdmin(admin.ModelAdmin):
    list_display = ('id', 'snapshot', 'auditor_type', 'created_at')
    list_filter = ('auditor_type',)
