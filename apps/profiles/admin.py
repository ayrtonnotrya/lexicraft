"""Django Admin da app `profiles` — interface aninhada com Inlines.

Fonte da verdade: docs/DATABASE_SCHEMA.md (Sessão 5).
"""
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
    list_display = (
        'name',
        'model_name',
        'is_active',
        'default_max_iterations',
        'default_max_budget_usd',
        'default_max_time_seconds',
    )
    list_filter = ('is_active', 'model_name')
    search_fields = ('name', 'description')
    inlines = [QualityAxisInline, SystemPromptInline]

    fieldsets = (
        (None, {
            'fields': ('name', 'model_name', 'is_active', 'description'),
        }),
        ('Limites Globais (Default)', {
            'fields': ('default_max_iterations', 'default_max_budget_usd', 'default_max_time_seconds'),
        }),
    )


@admin.register(QualityAxis)
class QualityAxisAdmin(admin.ModelAdmin):
    list_display = ('name', 'profile', 'weight', 'base_score')
    list_filter = ('profile',)
    search_fields = ('name',)


@admin.register(SystemPrompt)
class SystemPromptAdmin(admin.ModelAdmin):
    list_display = ('role_type', 'profile')
    list_filter = ('profile', 'role_type')
