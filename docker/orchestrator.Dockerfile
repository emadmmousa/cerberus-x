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
COPY playbooks/ /app/playbooks/

ENV PYTHONPATH=/app/src
ENV REDIS_URL=redis://redis:6379

EXPOSE 5000

CMD ["python", "-m", "orchestrator.dashboard"]