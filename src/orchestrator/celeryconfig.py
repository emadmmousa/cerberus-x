import os
from urllib.parse import quote


def _redis_url() -> str:
    """Build the Celery broker/backend URL.

    Prefer REDIS_HOST (+ REDIS_PASSWORD) when set so Kubernetes/Compose host
    env wins over a stale image ENV like REDIS_URL=redis://redis:6379.
    """
    explicit = os.getenv("REDIS_URL")
    password = os.getenv("REDIS_PASSWORD")
    host = os.getenv("REDIS_HOST")
    port = os.getenv("REDIS_PORT", "6379")
    db = os.getenv("REDIS_DB", "0")

    if explicit and (
        "$(REDIS_PASSWORD)" in explicit or explicit.startswith("redis://:$(REDIS")
    ):
        explicit = None

    if host:
        if password:
            return f"redis://:{quote(password, safe='')}@{host}:{port}/{db}"
        return f"redis://{host}:{port}/{db}"

    if explicit:
        return explicit

    host = "localhost"
    if password:
        return f"redis://:{quote(password, safe='')}@{host}:{port}/{db}"
    return f"redis://{host}:{port}/{db}"


REDIS_URL = _redis_url()

broker_url = REDIS_URL
result_backend = REDIS_URL
task_serializer = "json"
result_serializer = "json"
accept_content = ["json"]
timezone = "UTC"
enable_utc = True
task_track_started = True
task_time_limit = 30 * 60  # 30 minutes
task_soft_time_limit = 25 * 60
worker_prefetch_multiplier = 4
broker_connection_retry_on_startup = True
