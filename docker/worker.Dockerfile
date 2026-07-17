FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    nmap \
    whatweb \
    gobuster \
    sqlmap \
    dirb \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ /app/src/

ENV PYTHONPATH=/app/src
ENV REDIS_URL=redis://redis:6379

CMD ["celery", "-A", "orchestrator.tasks", "worker", "--concurrency=8", "--loglevel=info"]