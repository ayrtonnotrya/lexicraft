from django.apps import AppConfig


class OrchestratorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.orchestrator'
    label = 'orchestrator'
    verbose_name = 'Orquestrador'

    def ready(self) -> None:
        from . import signals  # noqa: F401
