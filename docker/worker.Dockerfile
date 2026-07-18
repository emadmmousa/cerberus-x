FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    nmap \
    whatweb \
    gobuster \
    sqlmap \
    dirb \
    curl \
    unzip \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install nuclei from GitHub release (versioned asset name + arch)
RUN set -eux; \
    ARCH="$(uname -m | sed 's/x86_64/amd64/;s/aarch64/arm64/')"; \
    VERSION="$(python -c "import json,urllib.request; print(json.load(urllib.request.urlopen('https://api.github.com/repos/projectdiscovery/nuclei/releases/latest'))['tag_name'].lstrip('v'))")"; \
    curl -fsSL -o /tmp/nuclei.zip \
      "https://github.com/projectdiscovery/nuclei/releases/download/v${VERSION}/nuclei_${VERSION}_linux_${ARCH}.zip"; \
    unzip -o /tmp/nuclei.zip -d /tmp/nuclei; \
    mv /tmp/nuclei/nuclei /usr/local/bin/nuclei; \
    chmod +x /usr/local/bin/nuclei; \
    rm -rf /tmp/nuclei /tmp/nuclei.zip; \
    nuclei -update-templates

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ /app/src/

ENV PYTHONPATH=/app/src
ENV REDIS_URL=redis://redis:6379

CMD ["celery", "-A", "orchestrator.tasks", "worker", "--concurrency=8", "--loglevel=info"]
