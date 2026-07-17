from celery import Celery

app = Celery('orchestrator')
app.config_from_object('orchestrator.celeryconfig')

# Autodiscover tasks
app.autodiscover_tasks(['orchestrator'])