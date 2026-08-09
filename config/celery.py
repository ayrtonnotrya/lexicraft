"""
Configuração do Celery para o LexiCraft.

O loop agêntico (Redator -> Guard-rail -> Tribunal -> Math Engine) roda em
workers assíncronos, isolado das threads HTTP síncronas do Django.
"""
import os

from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.local')

app = Celery('lexicraft')
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-descobre tasks registradas nos módulos `tasks` de cada app instalada.
app.autodiscover_tasks()

# Agenda do Beat: Ceifador de Tarefas Zumbis roda de 1 em 1 minuto.
app.conf.beat_schedule = {
    'reap-zombie-tasks-every-minute': {
        'task': 'orchestrator.reap_zombie_tasks',
        'schedule': 60.0,  # 60 segundos
    },
}
