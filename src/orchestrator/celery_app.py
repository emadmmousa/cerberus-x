import os

from celery import Celery
from celery.schedules import crontab

app = Celery("orchestrator")
app.config_from_object("orchestrator.celeryconfig")

# Autodiscover orchestrator + optional worker helpers (dynamic playbooks).
app.autodiscover_tasks(["orchestrator", "workers"])


def run_scale_workers_tick():
    from orchestrator.ml.flags import effective_auto_scale

    if not effective_auto_scale():
        return {"skipped": True, "reason": "auto_scale_off"}
    from workers.scaling import DynamicScaler

    return DynamicScaler().scale_workers()


def run_learning_tick():
    from orchestrator.ml.flags import effective_learning_tick
    from orchestrator.ml.harvest import run_learning_tick as harvest

    if not effective_learning_tick():
        return {"skipped": True, "reason": "learning_tick_off"}
    return harvest()


def run_daily_pipeline():
    from orchestrator.ml.auto_train import run_daily_pipeline as pipeline
    from orchestrator.ml.flags import effective_auto_train

    if not effective_auto_train():
        return {"skipped": True, "reason": "auto_train_off"}
    return pipeline()


@app.on_after_configure.connect
def _register_ops_periodic_tasks(sender, **kwargs):
    @app.task(name="workers.scale_workers_tick")
    def scale_workers_tick():
        return run_scale_workers_tick()

    @app.task(name="orchestrator.ml.learning_tick")
    def learning_tick_task():
        return run_learning_tick()

    @app.task(name="orchestrator.ml.daily_pipeline")
    def daily_pipeline_task():
        return run_daily_pipeline()

    sender.add_periodic_task(30.0, scale_workers_tick.s(), name="scale-workers")
    sender.add_periodic_task(60.0, learning_tick_task.s(), name="learning-tick")
    hour = int(os.environ.get("FIREBREAK_AUTO_TRAIN_HOUR") or "3")
    sender.add_periodic_task(
        crontab(minute=0, hour=max(0, min(hour, 23))),
        daily_pipeline_task.s(),
        name="daily-ml-pipeline",
    )
