FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends --fix-missing \
    nmap \
    masscan \
    whatweb \
    gobuster \
    sqlmap \
    dirb \
    john \
    hashcat \
    curl \
    unzip \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Arch-aware GitHub release helpers (amd64 / arm64)
RUN set -eux; \
    MACHINE="$(uname -m)"; \
    ARCH="$(echo "${MACHINE}" | sed 's/x86_64/amd64/;s/aarch64/arm64/')"; \
    \
    # rustscan
    RUSTSCAN_VERSION="$(python -c "import json,urllib.request; print(json.load(urllib.request.urlopen('https://api.github.com/repos/RustScan/RustScan/releases/latest'))['tag_name'].lstrip('v'))")"; \
    case "${MACHINE}" in \
      aarch64) RUSTSCAN_ASSET="aarch64-linux-rustscan.zip" ;; \
      x86_64)  RUSTSCAN_ASSET="x86_64-linux-rustscan.tar.gz.zip" ;; \
      *) echo "Unsupported architecture: ${MACHINE}" >&2; exit 1 ;; \
    esac; \
    curl -fsSL -o /tmp/rustscan.zip \
      "https://github.com/RustScan/RustScan/releases/download/${RUSTSCAN_VERSION}/${RUSTSCAN_ASSET}"; \
    mkdir -p /tmp/rustscan; \
    unzip -o /tmp/rustscan.zip -d /tmp/rustscan; \
    if [ -f /tmp/rustscan/rustscan ]; then \
      mv /tmp/rustscan/rustscan /usr/local/bin/rustscan; \
    else \
      tar -xzf /tmp/rustscan/*.tar.gz -C /tmp/rustscan; \
      find /tmp/rustscan -type f -name rustscan -exec mv {} /usr/local/bin/rustscan \; ; \
    fi; \
    chmod +x /usr/local/bin/rustscan; \
    rm -rf /tmp/rustscan /tmp/rustscan.zip; \
    \
    # ffuf
    FFUF_VERSION="$(python -c "import json,urllib.request; print(json.load(urllib.request.urlopen('https://api.github.com/repos/ffuf/ffuf/releases/latest'))['tag_name'].lstrip('v'))")"; \
    curl -fsSL -o /tmp/ffuf.tar.gz \
      "https://github.com/ffuf/ffuf/releases/download/v${FFUF_VERSION}/ffuf_${FFUF_VERSION}_linux_${ARCH}.tar.gz"; \
    tar -xzf /tmp/ffuf.tar.gz -C /tmp; \
    mv /tmp/ffuf /usr/local/bin/ffuf; \
    chmod +x /usr/local/bin/ffuf; \
    rm -f /tmp/ffuf.tar.gz; \
    \
    # nuclei (versioned asset name)
    NUCLEI_VERSION="$(python -c "import json,urllib.request; print(json.load(urllib.request.urlopen('https://api.github.com/repos/projectdiscovery/nuclei/releases/latest'))['tag_name'].lstrip('v'))")"; \
    curl -fsSL -o /tmp/nuclei.zip \
      "https://github.com/projectdiscovery/nuclei/releases/download/v${NUCLEI_VERSION}/nuclei_${NUCLEI_VERSION}_linux_${ARCH}.zip"; \
    unzip -o /tmp/nuclei.zip -d /tmp/nuclei; \
    mv /tmp/nuclei/nuclei /usr/local/bin/nuclei; \
    chmod +x /usr/local/bin/nuclei; \
    rm -rf /tmp/nuclei /tmp/nuclei.zip; \
    nuclei -update-templates

RUN apt-get update && apt-get install -y --no-install-recommends --fix-missing \
    git \
    && pip install --no-cache-dir \
      "git+https://github.com/laramies/theHarvester.git" \
    && apt-get purge -y git \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /app/tools && \
    curl -fsSL -o /app/tools/winPEASx64.exe \
      https://github.com/peass-ng/PEASS-ng/releases/latest/download/winPEASx64.exe && \
    curl -fsSL -o /app/tools/linpeas.sh \
      https://github.com/peass-ng/PEASS-ng/releases/latest/download/linpeas.sh && \
    chmod +x /app/tools/linpeas.sh

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ /app/src/

ENV PYTHONPATH=/app/src
ENV REDIS_URL=redis://redis:6379

CMD ["celery", "-A", "orchestrator.tasks", "worker", "--concurrency=8", "--loglevel=info"]
