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
    nuclei -update-templates; \
    \
    # katana
    KATANA_VERSION="$(python -c "import json,urllib.request; print(json.load(urllib.request.urlopen('https://api.github.com/repos/projectdiscovery/katana/releases/latest'))['tag_name'].lstrip('v'))")"; \
    curl -fsSL -o /tmp/katana.zip \
      "https://github.com/projectdiscovery/katana/releases/download/v${KATANA_VERSION}/katana_${KATANA_VERSION}_linux_${ARCH}.zip"; \
    unzip -o /tmp/katana.zip -d /tmp/katana; \
    mv /tmp/katana/katana /usr/local/bin/katana; \
    chmod +x /usr/local/bin/katana; \
    rm -rf /tmp/katana /tmp/katana.zip; \
    \
    # subfinder + gau (passive OSINT scrapers)
    SUBFINDER_VERSION="$(python -c "import json,urllib.request; print(json.load(urllib.request.urlopen('https://api.github.com/repos/projectdiscovery/subfinder/releases/latest'))['tag_name'].lstrip('v'))")"; \
    curl -fsSL -o /tmp/subfinder.zip \
      "https://github.com/projectdiscovery/subfinder/releases/download/v${SUBFINDER_VERSION}/subfinder_${SUBFINDER_VERSION}_linux_${ARCH}.zip"; \
    unzip -o /tmp/subfinder.zip -d /tmp/subfinder; \
    mv /tmp/subfinder/subfinder /usr/local/bin/subfinder; \
    chmod +x /usr/local/bin/subfinder; \
    rm -rf /tmp/subfinder /tmp/subfinder.zip; \
    GAU_VERSION="$(python -c "import json,urllib.request; print(json.load(urllib.request.urlopen('https://api.github.com/repos/lc/gau/releases/latest'))['tag_name'].lstrip('v'))")"; \
    curl -fsSL -o /tmp/gau.tar.gz \
      "https://github.com/lc/gau/releases/download/v${GAU_VERSION}/gau_${GAU_VERSION}_linux_${ARCH}.tar.gz"; \
    tar -xzf /tmp/gau.tar.gz -C /tmp; \
    mv /tmp/gau /usr/local/bin/gau; \
    chmod +x /usr/local/bin/gau; \
    rm -f /tmp/gau.tar.gz

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
      "bloodhound" \
      "sherlock-project"

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

# Sliver C2 (BishopFox) — optional post-exploitation C2 for authorized engagements.
# Arch-aware: aarch64->arm64, x86_64->amd64. Server binary self-fetches deps on first run.
RUN set -eux; \
    MACHINE="$(uname -m)"; \
    case "${MACHINE}" in \
      aarch64) SLIVER_ARCH="arm64" ;; \
      x86_64)  SLIVER_ARCH="amd64" ;; \
      *) echo "Unsupported architecture: ${MACHINE}" >&2; exit 1 ;; \
    esac; \
    for attempt in 1 2 3 4 5; do \
      curl -fsSL --retry 3 --retry-delay 5 --retry-all-errors \
        -o /usr/local/bin/sliver-server \
        "https://github.com/BishopFox/sliver/releases/latest/download/sliver-server_linux-${SLIVER_ARCH}" && break; \
      echo "sliver-server download failed (attempt ${attempt}); retrying..." >&2; \
      sleep $((attempt * 5)); \
    done; \
    test -s /usr/local/bin/sliver-server; \
    for attempt in 1 2 3 4 5; do \
      curl -fsSL --retry 3 --retry-delay 5 --retry-all-errors \
        -o /usr/local/bin/sliver-client \
        "https://github.com/BishopFox/sliver/releases/latest/download/sliver-client_linux-${SLIVER_ARCH}" && break; \
      echo "sliver-client download failed (attempt ${attempt}); retrying..." >&2; \
      sleep $((attempt * 5)); \
    done; \
    test -s /usr/local/bin/sliver-client; \
    chmod +x /usr/local/bin/sliver-server /usr/local/bin/sliver-client

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ /app/src/

# ProjectDiscovery httpx (pip installs a conflicting `httpx` Python CLI).
RUN set -eux; \
    MACHINE="$(uname -m)"; \
    ARCH="$(echo "${MACHINE}" | sed 's/x86_64/amd64/;s/aarch64/arm64/')"; \
    HTTPX_VERSION="$(python -c "import json,urllib.request; print(json.load(urllib.request.urlopen('https://api.github.com/repos/projectdiscovery/httpx/releases/latest'))['tag_name'].lstrip('v'))")"; \
    curl -fsSL -o /tmp/pdhttpx.zip \
      "https://github.com/projectdiscovery/httpx/releases/download/v${HTTPX_VERSION}/httpx_${HTTPX_VERSION}_linux_${ARCH}.zip"; \
    unzip -o /tmp/pdhttpx.zip -d /tmp/pdhttpx; \
    mv /tmp/pdhttpx/httpx /usr/local/bin/pd-httpx; \
    chmod +x /usr/local/bin/pd-httpx; \
    rm -rf /tmp/pdhttpx /tmp/pdhttpx.zip

# Extended aggressive-era toolchain
RUN set -eux; \
    MACHINE="$(uname -m)"; \
    ARCH="$(echo "${MACHINE}" | sed 's/x86_64/amd64/;s/aarch64/arm64/')"; \
    \
    NAABU_VERSION="$(python -c "import json,urllib.request; print(json.load(urllib.request.urlopen('https://api.github.com/repos/projectdiscovery/naabu/releases/latest'))['tag_name'].lstrip('v'))")"; \
    curl -fsSL -o /tmp/naabu.zip "https://github.com/projectdiscovery/naabu/releases/download/v${NAABU_VERSION}/naabu_${NAABU_VERSION}_linux_${ARCH}.zip"; \
    unzip -o /tmp/naabu.zip -d /tmp/naabu; mv /tmp/naabu/naabu /usr/local/bin/naabu; chmod +x /usr/local/bin/naabu; rm -rf /tmp/naabu /tmp/naabu.zip; \
    \
    DNSX_VERSION="$(python -c "import json,urllib.request; print(json.load(urllib.request.urlopen('https://api.github.com/repos/projectdiscovery/dnsx/releases/latest'))['tag_name'].lstrip('v'))")"; \
    curl -fsSL -o /tmp/dnsx.zip "https://github.com/projectdiscovery/dnsx/releases/download/v${DNSX_VERSION}/dnsx_${DNSX_VERSION}_linux_${ARCH}.zip"; \
    unzip -o /tmp/dnsx.zip -d /tmp/dnsx; mv /tmp/dnsx/dnsx /usr/local/bin/dnsx; chmod +x /usr/local/bin/dnsx; rm -rf /tmp/dnsx /tmp/dnsx.zip; \
    \
    FEROX_VERSION="$(python -c "import json,urllib.request; print(json.load(urllib.request.urlopen('https://api.github.com/repos/epi052/feroxbuster/releases/latest'))['tag_name'].lstrip('v'))")"; \
    curl -fsSL -o /tmp/feroxbuster.zip "https://github.com/epi052/feroxbuster/releases/download/v${FEROX_VERSION}/x86_64-unknown-linux-musl.zip"; \
    if [ "${MACHINE}" = "aarch64" ]; then \
      curl -fsSL -o /tmp/feroxbuster.zip "https://github.com/epi052/feroxbuster/releases/download/v${FEROX_VERSION}/aarch64-unknown-linux-musl.zip"; \
    fi; \
    unzip -o /tmp/feroxbuster.zip -d /tmp/feroxbuster; mv /tmp/feroxbuster/feroxbuster /usr/local/bin/feroxbuster; chmod +x /usr/local/bin/feroxbuster; rm -rf /tmp/feroxbuster /tmp/feroxbuster.zip; \
    \
    DALFOX_VERSION="$(python -c "import json,urllib.request; print(json.load(urllib.request.urlopen('https://api.github.com/repos/hahwul/dalfox/releases/latest'))['tag_name'].lstrip('v'))")"; \
    curl -fsSL -o /tmp/dalfox.tar.gz "https://github.com/hahwul/dalfox/releases/download/v${DALFOX_VERSION}/dalfox_${DALFOX_VERSION}_linux_${ARCH}.tar.gz"; \
    tar -xzf /tmp/dalfox.tar.gz -C /tmp; mv /tmp/dalfox /usr/local/bin/dalfox; chmod +x /usr/local/bin/dalfox; rm -f /tmp/dalfox.tar.gz; \
    \
    AMASS_VERSION="$(python -c "import json,urllib.request; print(json.load(urllib.request.urlopen('https://api.github.com/repos/owasp-amass/amass/releases/latest'))['tag_name'].lstrip('v'))")"; \
    curl -fsSL -o /tmp/amass.zip "https://github.com/owasp-amass/amass/releases/download/v${AMASS_VERSION}/amass_Linux_${ARCH}.zip"; \
    unzip -o /tmp/amass.zip -d /tmp/amass; find /tmp/amass -type f -name amass -exec mv {} /usr/local/bin/amass \; ; chmod +x /usr/local/bin/amass; rm -rf /tmp/amass /tmp/amass.zip; \
    \
    if [ "${MACHINE}" = "aarch64" ]; then \
      apt-get update && apt-get install -y --no-install-recommends golang-go \
      && go install github.com/tomnomnom/waybackurls@latest \
      && mv /root/go/bin/waybackurls /usr/local/bin/waybackurls \
      && apt-get purge -y golang-go && apt-get autoremove -y && rm -rf /var/lib/apt/lists/* /root/go; \
    else \
      curl -fsSL -o /usr/local/bin/waybackurls "https://github.com/tomnomnom/waybackurls/releases/latest/download/waybackurls-linux-amd64"; \
      chmod +x /usr/local/bin/waybackurls; \
    fi

RUN apt-get update && apt-get install -y --no-install-recommends sslscan \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 https://github.com/commixproject/commix.git /opt/commix \
    && pip install --no-cache-dir arjun enum4linux-ng

RUN apt-get update && apt-get install -y --no-install-recommends ruby ruby-dev \
    && gem install --no-document wpscan \
    && apt-get purge -y ruby-dev \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONPATH=/app/src

CMD ["celery", "-A", "orchestrator.tasks", "worker", "--concurrency=8", "--loglevel=info", "--autoreload"]
