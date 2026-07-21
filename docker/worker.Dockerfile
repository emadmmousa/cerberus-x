FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends --fix-missing \
    nmap \
    masscan \
    zmap \
    whatweb \
    gobuster \
    sqlmap \
    dirb \
    hydra \
    john \
    hashcat \
    curl \
    unzip \
    ca-certificates \
    git \
    perl \
    libnet-ssleay-perl \
    libio-socket-ssl-perl \
    libjson-perl \
    libxml-writer-perl \
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
    # nuclei
    NUCLEI_VERSION="$(python -c "import json,urllib.request; print(json.load(urllib.request.urlopen('https://api.github.com/repos/projectdiscovery/nuclei/releases/latest'))['tag_name'].lstrip('v'))")"; \
    curl -fsSL -o /tmp/nuclei.zip \
      "https://github.com/projectdiscovery/nuclei/releases/download/v${NUCLEI_VERSION}/nuclei_${NUCLEI_VERSION}_linux_${ARCH}.zip"; \
    unzip -o /tmp/nuclei.zip -d /tmp/nuclei; \
    mv /tmp/nuclei/nuclei /usr/local/bin/nuclei; \
    chmod +x /usr/local/bin/nuclei; \
    rm -rf /tmp/nuclei /tmp/nuclei.zip; \
    nuclei -update-templates

# Nikto (not in Debian 13) + XSStrike from upstream
RUN set -eux; \
    git clone --depth 1 https://github.com/sullo/nikto.git /opt/nikto; \
    ln -sf /opt/nikto/program/nikto.pl /usr/local/bin/nikto; \
    chmod +x /opt/nikto/program/nikto.pl; \
    git clone --depth 1 https://github.com/s0md3v/XSStrike.git /opt/XSStrike; \
    pip install --no-cache-dir -r /opt/XSStrike/requirements.txt; \
    printf '%s\n' '#!/bin/sh' 'exec python /opt/XSStrike/xsstrike.py "$@"' > /usr/local/bin/xsstrike; \
    chmod +x /usr/local/bin/xsstrike

# Harden XSStrike against empty responses / 10-minute WAF sleeps
COPY docker/patches/xsstrike_harden.py /tmp/xsstrike_harden.py
RUN python /tmp/xsstrike_harden.py && rm -f /tmp/xsstrike_harden.py

# theHarvester + Impacket + BloodHound.py (system Python)
RUN pip install --no-cache-dir \
      "git+https://github.com/laramies/theHarvester.git" \
      "impacket" \
      "bloodhound"

# Responder (LLMNR/NBT-NS helper) — binary on PATH for health + optional -I runs
RUN set -eux; \
    git clone --depth 1 https://github.com/lgandx/Responder.git /opt/Responder; \
    printf '%s\n' '#!/bin/sh' 'exec python /opt/Responder/Responder.py "$@"' > /usr/local/bin/responder; \
    chmod +x /usr/local/bin/responder /opt/Responder/Responder.py

# NetExec/CrackMapExec in an isolated venv (dnspython conflicts with theHarvester)
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential \
      python3-dev \
      libffi-dev \
      libssl-dev \
      rustc \
      cargo \
    && python -m venv /opt/netexec \
    && /opt/netexec/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/netexec/bin/pip install --no-cache-dir "git+https://github.com/Pennyw0rth/NetExec.git" \
    && ln -sf /opt/netexec/bin/nxc /usr/local/bin/nxc \
    && ln -sf /opt/netexec/bin/nxc /usr/local/bin/crackmapexec \
    && ln -sf /opt/netexec/bin/nxc /usr/local/bin/cme \
    && apt-get purge -y build-essential python3-dev libffi-dev libssl-dev rustc cargo \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/* /root/.cargo /root/.rustup

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

CMD ["celery", "-A", "orchestrator.tasks", "worker", "--concurrency=8", "--loglevel=info"]
