"""Rotas do Dashboard (Monólito Majestoso — Django + HTMX)."""
from django.urls import path

from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.dashboard_index, name='dashboard_index'),
    path('tasks/start/', views.start_task, name='start_task'),
    path('tasks/recent/', views.recent_tasks_partial, name='recent_tasks_partial'),
    path('tasks/<int:task_id>/', views.task_detail, name='task_detail'),
    path('tasks/<int:task_id>/status/', views.task_status_partial, name='task_status_partial'),
    path('tasks/<int:task_id>/cancel/', views.cancel_task, name='cancel_task'),
    path('tasks/<int:task_id>/snapshots/<int:snapshot_id>/', views.snapshot_partial, name='snapshot_partial'),
]
