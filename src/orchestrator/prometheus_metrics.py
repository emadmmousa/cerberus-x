from flask import Response
from prometheus_client import REGISTRY, Counter, Gauge, Histogram, generate_latest

jobs_total = Counter("cerberus_jobs_total", "Total jobs executed", ["tool", "phase"])
jobs_success = Counter("cerberus_jobs_success", "Successful jobs", ["tool", "phase"])
jobs_failed = Counter("cerberus_jobs_failed", "Failed jobs", ["tool", "phase"])
queue_length = Gauge("cerberus_queue_length", "Celery queue length")
job_duration = Histogram(
    "cerberus_job_duration_seconds",
    "Job execution duration",
    ["tool"],
)


def track_job(tool, phase, duration, success):
    """Track job metrics."""
    tool_name = str(tool or "unknown")
    phase_name = str(phase or "unknown")
    jobs_total.labels(tool=tool_name, phase=phase_name).inc()
    if success:
        jobs_success.labels(tool=tool_name, phase=phase_name).inc()
    else:
        jobs_failed.labels(tool=tool_name, phase=phase_name).inc()
    job_duration.labels(tool=tool_name).observe(float(duration or 0.0))


def update_queue_length(length):
    """Update queue length gauge."""
    queue_length.set(int(length or 0))


def metrics_endpoint():
    """Flask endpoint for Prometheus."""
    return Response(generate_latest(REGISTRY), mimetype="text/plain; version=0.0.4")
