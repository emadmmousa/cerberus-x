from celery import Celery

app = Celery("orchestrator")
app.config_from_object("orchestrator.celeryconfig")

# Autodiscover orchestrator + optional worker helpers (dynamic playbooks).
app.autodiscover_tasks(["orchestrator", "workers"])


@app.on_after_configure.connect
def _register_optional_scale_task(sender, **kwargs):
    """Optional K8s scaler beat task — skipped when disabled."""
    import os

    if os.environ.get("CERBERUS_AUTO_SCALE", "false").lower() not in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return

    @app.task(name="workers.scale_workers_tick")
    def scale_workers_tick():
        from workers.scaling import DynamicScaler

        return DynamicScaler().scale_workers()

    sender.add_periodic_task(30.0, scale_workers_tick.s(), name="scale-workers")
