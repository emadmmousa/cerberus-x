# Oxylabs Proxy + React Operator Console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add optional per-run Oxylabs routing via a worker-local credential-isolating forwarder, and replace the Jinja dashboard with a React + Vite dark tactical operator console.

**Architecture:** Celery tasks carry only `use_proxy` / `proxy_protocol`. Workers resolve tool-specific localhost proxy flags through `proxy_config`, while a local HTTP forwarder injects Oxylabs Basic auth. Flask serves the Vite-built SPA and keeps existing REST/Socket.IO contracts.

**Tech Stack:** Python 3.12, Celery, Flask, Flask-SocketIO, pytest, Vite, React 18, TypeScript, Docker multi-stage Node build, Kubernetes ConfigMap/Secret.

## Global Constraints

- Proxy activation is per-run, default off.
- Default protocol is `http`; allowed values: `http`, `https`, `socks5h`.
- Unsupported tool/protocol combos run direct and record `proxy_skipped` (best-effort).
- Oxylabs credentials never appear in git, playbooks, Celery kwargs, tool argv, browser, or unredacted logs.
- Secrets live on workers only (`OXYLABS_PROXY_USERNAME` / `OXYLABS_PROXY_PASSWORD`).
- UI never collects Oxylabs username/password.
- Findings rendering must not use `innerHTML` for untrusted payloads.
- Playbook `when` / `depends_on` enforcement is out of scope.
- Live Oxylabs calls are forbidden in CI (mock the upstream).
- Rotate any Oxylabs password previously shared in chat before production use.

## File Structure

| Path | Responsibility |
| --- | --- |
| `src/tools/proxy_config.py` | Env parsing, redaction, per-tool resolve |
| `src/tools/local_proxy.py` | Localhost HTTP forwarder with upstream auth |
| `src/tools/wrappers/*.py` | Apply resolved flags/env; attach `proxy` metadata |
| `src/orchestrator/tasks.py` | Pass `use_proxy` / `proxy_protocol` into tasks |
| `src/orchestrator/dashboard.py` | Accept run flags; serve SPA; optional proxy status |
| `frontend/` | Vite React TypeScript operator console |
| `src/orchestrator/static/app/` | Built SPA assets served by Flask |
| `.env.example`, `k8s/configmap.yaml`, `k8s/worker-deployment.yaml`, `k8s/secrets.yaml` | Document/wire non-secret + secret proxy env |
| `docker/orchestrator.Dockerfile` | Node build stage + copy static assets |
| `tests/test_proxy_config.py`, `tests/test_local_proxy.py`, wrapper/API/frontend tests | Coverage |

---

### Task 1: `proxy_config` module

**Files:**
- Create: `src/tools/proxy_config.py`
- Create: `tests/test_proxy_config.py`
- Modify: `.env.example`

**Interfaces:**
- Produces: `ALLOWED_PROTOCOLS = frozenset({"http", "https", "socks5h"})`
- Produces: `redact_proxy_url(url: str) -> str`
- Produces: `credentials_configured() -> bool`
- Produces: `local_proxy_url(protocol: str = "http") -> str`
- Produces: `upstream_proxy_url() -> str` (for forwarder only; includes encoded userinfo)
- Produces: `resolve_for_tool(tool: str, *, use_proxy: bool, protocol: str = "http") -> dict` with keys `mode`, `flags`, `env`, `note`, `local_proxy_url`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_proxy_config.py
import os
from tools import proxy_config


def test_disabled_by_default(monkeypatch):
    monkeypatch.delenv("OXYLABS_PROXY_USERNAME", raising=False)
    monkeypatch.delenv("OXYLABS_PROXY_PASSWORD", raising=False)
    result = proxy_config.resolve_for_tool("sqlmap", use_proxy=False)
    assert result["mode"] == "direct"
    assert result["flags"] == []
    assert result["env"] == {}
    assert result["local_proxy_url"] is None


def test_default_protocol_http(monkeypatch):
    monkeypatch.setenv("OXYLABS_PROXY_USERNAME", "user")
    monkeypatch.setenv("OXYLABS_PROXY_PASSWORD", "p@ss:word")
    monkeypatch.setenv("FIREBREAK_LOCAL_PROXY_PORT", "18080")
    result = proxy_config.resolve_for_tool("sqlmap", use_proxy=True)
    assert result["mode"] == "local_proxy"
    assert result["local_proxy_url"] == "http://127.0.0.1:18080"
    assert "--proxy" in result["flags"]
    assert "p@ss:word" not in " ".join(result["flags"])


def test_redact_proxy_url():
    url = "http://user:secret@pr.oxylabs.io:7777"
    assert proxy_config.redact_proxy_url(url) == "http://user:***@pr.oxylabs.io:7777"


def test_upstream_url_encodes_password(monkeypatch):
    monkeypatch.setenv("OXYLABS_PROXY_USERNAME", "customer-x")
    monkeypatch.setenv("OXYLABS_PROXY_PASSWORD", "p@ss:word")
    monkeypatch.setenv("OXYLABS_PROXY_HOST", "pr.oxylabs.io")
    monkeypatch.setenv("OXYLABS_PROXY_PORT", "7777")
    upstream = proxy_config.upstream_proxy_url()
    assert "p@ss:word" not in upstream  # must be percent-encoded
    assert "%40" in upstream or "%3A" in upstream
    assert proxy_config.redact_proxy_url(upstream).endswith("@pr.oxylabs.io:7777")


def test_sqlmap_flags_no_proxy_cred(monkeypatch):
    monkeypatch.setenv("OXYLABS_PROXY_USERNAME", "u")
    monkeypatch.setenv("OXYLABS_PROXY_PASSWORD", "p")
    result = proxy_config.resolve_for_tool("sqlmap", use_proxy=True, protocol="http")
    joined = " ".join(result["flags"])
    assert "--proxy-cred" not in joined
    assert result["flags"] == ["--proxy", "http://127.0.0.1:18080"]


def test_hydra_uses_env(monkeypatch):
    monkeypatch.setenv("OXYLABS_PROXY_USERNAME", "u")
    monkeypatch.setenv("OXYLABS_PROXY_PASSWORD", "p")
    result = proxy_config.resolve_for_tool("hydra", use_proxy=True, protocol="http")
    assert result["mode"] == "local_proxy"
    assert result["env"]["HYDRA_PROXY_HTTP"] == "http://127.0.0.1:18080"


def test_unsupported_protocol_for_nikto_socks(monkeypatch):
    monkeypatch.setenv("OXYLABS_PROXY_USERNAME", "u")
    monkeypatch.setenv("OXYLABS_PROXY_PASSWORD", "p")
    result = proxy_config.resolve_for_tool("nikto", use_proxy=True, protocol="socks5h")
    assert result["mode"] == "unsupported"
    assert result["note"]
    assert result["flags"] == []


def test_use_proxy_true_without_credentials_is_direct(monkeypatch):
    monkeypatch.delenv("OXYLABS_PROXY_USERNAME", raising=False)
    monkeypatch.delenv("OXYLABS_PROXY_PASSWORD", raising=False)
    result = proxy_config.resolve_for_tool("ffuf", use_proxy=True)
    assert result["mode"] == "unsupported"
    assert "credential" in (result["note"] or "").lower() or "not configured" in (result["note"] or "").lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_proxy_config.py -v`  
Expected: FAIL with `ModuleNotFoundError` or `ImportError` for `tools.proxy_config`

- [ ] **Step 3: Implement `src/tools/proxy_config.py`**

```python
from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote, urlparse, urlunparse

ALLOWED_PROTOCOLS = frozenset({"http", "https", "socks5h"})

# tool -> how to attach local proxy for HTTP (extend as needed)
_HTTP_TOOL_BUILDERS = {
    "sqlmap": lambda url: {"flags": ["--proxy", url], "env": {}},
    "ffuf": lambda url: {"flags": ["-x", url], "env": {}},
    "gobuster": lambda url: {"flags": ["--proxy", url], "env": {"HTTP_PROXY": url, "HTTPS_PROXY": url, "http_proxy": url, "https_proxy": url}},
    "nuclei": lambda url: {"flags": ["-proxy", url], "env": {}},
    "whatweb": lambda url: {"flags": ["--proxy", f"{urlparse(url).hostname}:{urlparse(url).port}"], "env": {}},
    "nikto": lambda url: {"flags": ["-useproxy", url], "env": {}},
    "hydra": lambda url: {"flags": [], "env": {"HYDRA_PROXY_HTTP": url}},
    "xsstrike": lambda url: {"flags": [], "env": {"HTTP_PROXY": url, "HTTPS_PROXY": url, "http_proxy": url, "https_proxy": url}},
}

# tools that cannot use socks5h via this matrix in v1
_SOCKS_UNSUPPORTED = frozenset({"nikto", "whatweb", "xsstrike"})


def credentials_configured() -> bool:
    return bool(os.getenv("OXYLABS_PROXY_USERNAME") and os.getenv("OXYLABS_PROXY_PASSWORD"))


def local_proxy_url(protocol: str = "http") -> str:
    host = os.getenv("FIREBREAK_LOCAL_PROXY_HOST", "127.0.0.1")
    port = os.getenv("FIREBREAK_LOCAL_PROXY_PORT", "18080")
    scheme = "socks5h" if protocol == "socks5h" else "http"
    return f"{scheme}://{host}:{port}"


def upstream_proxy_url() -> str:
    user = quote(os.environ["OXYLABS_PROXY_USERNAME"], safe="")
    password = quote(os.environ["OXYLABS_PROXY_PASSWORD"], safe="")
    host = os.getenv("OXYLABS_PROXY_HOST", "pr.oxylabs.io")
    port = os.getenv("OXYLABS_PROXY_PORT", "7777")
    protocol = os.getenv("OXYLABS_PROXY_PROTOCOL", "http")
    if protocol not in ALLOWED_PROTOCOLS:
        protocol = "http"
    scheme = "socks5h" if protocol == "socks5h" else "http"
    return f"{scheme}://{user}:{password}@{host}:{port}"


def redact_proxy_url(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.password:
        return url
    netloc = parsed.hostname or ""
    if parsed.port:
        netloc = f"{netloc}:{parsed.port}"
    user = parsed.username or ""
    netloc = f"{user}:***@{netloc}" if user else f"***@{netloc}"
    return urlunparse(parsed._replace(netloc=netloc))


def resolve_for_tool(tool: str, *, use_proxy: bool, protocol: str = "http") -> dict[str, Any]:
    protocol = protocol if protocol in ALLOWED_PROTOCOLS else "http"
    if not use_proxy:
        return {"mode": "direct", "flags": [], "env": {}, "note": None, "local_proxy_url": None}
    if not credentials_configured():
        return {
            "mode": "unsupported",
            "flags": [],
            "env": {},
            "note": "proxy credentials not configured on worker",
            "local_proxy_url": None,
        }
    if protocol == "socks5h" and tool in _SOCKS_UNSUPPORTED:
        return {
            "mode": "unsupported",
            "flags": [],
            "env": {},
            "note": f"{tool} does not support socks5h in this release",
            "local_proxy_url": None,
        }
    if protocol == "https":
        # v1 forwarder is HTTP-upstream first-class; treat https request as unsupported
        # unless tool can still use local http forwarder — prefer local http URL for tools.
        protocol = "http"
    builder = _HTTP_TOOL_BUILDERS.get(tool)
    if builder is None:
        return {
            "mode": "unsupported",
            "flags": [],
            "env": {},
            "note": f"{tool} has no proxy adapter; running direct",
            "local_proxy_url": None,
        }
    url = local_proxy_url("http")
    built = builder(url)
    return {
        "mode": "local_proxy",
        "flags": built["flags"],
        "env": built["env"],
        "note": None,
        "local_proxy_url": url,
    }
```

- [ ] **Step 4: Document env vars in `.env.example`** (blank credentials only)

Append:

```bash
# --- Oxylabs residential proxy (workers only; never commit real values) ---
OXYLABS_PROXY_HOST=pr.oxylabs.io
OXYLABS_PROXY_PORT=7777
OXYLABS_PROXY_PROTOCOL=http
OXYLABS_PROXY_USERNAME=
OXYLABS_PROXY_PASSWORD=
FIREBREAK_LOCAL_PROXY_HOST=127.0.0.1
FIREBREAK_LOCAL_PROXY_PORT=18080
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_proxy_config.py -v`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/tools/proxy_config.py tests/test_proxy_config.py .env.example
git commit -m "$(cat <<'EOF'
feat(proxy): add proxy_config resolver and redaction

EOF
)"
```

---

### Task 2: Local credential-isolating HTTP forwarder

**Files:**
- Create: `src/tools/local_proxy.py`
- Create: `tests/test_local_proxy.py`
- Modify: `requirements.txt` (only if a tiny dep is required; prefer stdlib)

**Interfaces:**
- Produces: `class LocalProxyServer` with `start()`, `stop()`, `healthy() -> bool`, `address -> tuple[str, int]`
- Produces: `ensure_local_proxy() -> LocalProxyServer` (idempotent singleton for worker process)
- Consumes: `proxy_config.upstream_proxy_url()`, `proxy_config.redact_proxy_url()`

- [ ] **Step 1: Write failing tests** using a mock upstream TCP server (no Oxylabs):

```python
# tests/test_local_proxy.py
import base64
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from tools import local_proxy, proxy_config


def test_healthy_after_start(monkeypatch):
    monkeypatch.setenv("OXYLABS_PROXY_USERNAME", "u")
    monkeypatch.setenv("OXYLABS_PROXY_PASSWORD", "p")
    monkeypatch.setenv("FIREBREAK_LOCAL_PROXY_PORT", "0")  # ephemeral if supported
    server = local_proxy.LocalProxyServer()
    server.start()
    try:
        assert server.healthy() is True
    finally:
        server.stop()


def test_errors_never_include_password(monkeypatch):
    monkeypatch.setenv("OXYLABS_PROXY_USERNAME", "u")
    monkeypatch.setenv("OXYLABS_PROXY_PASSWORD", "super-secret")
    err = local_proxy.ProxyForwardError("upstream failed for " + proxy_config.upstream_proxy_url())
    assert "super-secret" not in str(err)
    assert "***" in str(err) or "super-secret" not in repr(err)
```

Implement `ProxyForwardError` to redact via `redact_proxy_url` on the message.

- [ ] **Step 2: Run tests — expect FAIL** (`ModuleNotFoundError`)

- [ ] **Step 3: Implement stdlib threaded HTTP proxy**

Minimal behavior for v1:
- Listen on `FIREBREAK_LOCAL_PROXY_HOST:FIREBREAK_LOCAL_PROXY_PORT`
- Support absolute-form HTTP requests and `CONNECT`
- Open a connection to Oxylabs (`OXYLABS_PROXY_HOST:PORT`) and send the client request with `Proxy-Authorization: Basic <b64(user:pass)>`
- Do not log upstream URLs with plaintext passwords
- `healthy()` = listening socket accepts a connection or bound flag is true
- If protocol env is `socks5h`, `start()` may raise `ProxyForwardError("socks5h forwarder not implemented; use http")` — callers treat as unhealthy and tools fall back via `resolve_for_tool` / task guard

Keep the implementation in one file (~150–250 lines). Prefer stdlib `socket` + `threading` + `select`.

- [ ] **Step 4: Run `pytest tests/test_local_proxy.py tests/test_proxy_config.py -v` — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add src/tools/local_proxy.py tests/test_local_proxy.py
git commit -m "$(cat <<'EOF'
feat(proxy): add localhost credential-isolating forwarder

EOF
)"
```

---

### Task 3: Wire wrappers to `resolve_for_tool`

**Files:**
- Modify: `src/tools/wrappers/sqlmap.py`
- Modify: `src/tools/wrappers/hydra.py`
- Modify: `src/tools/wrappers/gobuster.py`
- Modify: `src/tools/wrappers/ffuf.py`
- Modify: `src/tools/wrappers/nikto.py`
- Modify: `src/tools/wrappers/nuclei.py`
- Modify: `src/tools/wrappers/whatweb.py`
- Modify: `src/tools/wrappers/xsstrike.py`
- Create: `tests/test_proxy_wrappers.py`

**Interfaces:**
- Consumes: `resolve_for_tool(tool, use_proxy=..., protocol=...)`
- Change each `scan(...)` signature to accept optional `use_proxy: bool = False`, `proxy_protocol: str = "http"`
- Every result dict gains optional `"proxy": {"enabled": bool, "protocol": str, "mode": str, "note": str | None}`

- [ ] **Step 1: Write failing wrapper tests** (mock `subprocess`):

```python
# tests/test_proxy_wrappers.py
from unittest.mock import patch
from tools.wrappers import sqlmap, hydra, gobuster


def test_sqlmap_adds_proxy_flag_without_secrets(monkeypatch):
    monkeypatch.setenv("OXYLABS_PROXY_USERNAME", "u")
    monkeypatch.setenv("OXYLABS_PROXY_PASSWORD", "secret")
    with patch("tools.wrappers.sqlmap.subprocess.check_output", return_value="ok") as mock:
        result = sqlmap.scan("example.com", use_proxy=True, proxy_protocol="http")
    cmd = mock.call_args[0][0]
    assert "--proxy" in cmd
    assert "http://127.0.0.1:18080" in cmd
    assert "secret" not in cmd
    assert result["proxy"]["mode"] == "local_proxy"


def test_sqlmap_proxy_off_unchanged(monkeypatch):
    with patch("tools.wrappers.sqlmap.subprocess.check_output", return_value="ok") as mock:
        sqlmap.scan("example.com", use_proxy=False)
    cmd = mock.call_args[0][0]
    assert "--proxy" not in cmd


def test_hydra_sets_env(monkeypatch):
    monkeypatch.setenv("OXYLABS_PROXY_USERNAME", "u")
    monkeypatch.setenv("OXYLABS_PROXY_PASSWORD", "secret")
    with patch("tools.wrappers.hydra.subprocess.run") as mock:
        mock.return_value.stdout = ""
        mock.return_value.stderr = ""
        mock.return_value.returncode = 0
        hydra.scan("example.com", use_proxy=True)
    env = mock.call_args.kwargs.get("env")
    assert env is not None
    assert env["HYDRA_PROXY_HTTP"] == "http://127.0.0.1:18080"
    assert "secret" not in str(env)


def test_gobuster_preflight_inherits_proxy_env(monkeypatch):
    monkeypatch.setenv("OXYLABS_PROXY_USERNAME", "u")
    monkeypatch.setenv("OXYLABS_PROXY_PASSWORD", "secret")
    with patch("tools.wrappers.gobuster.subprocess.check_output", return_value="") as mock_run:
        with patch("tools.wrappers.gobuster._probe_exclude_length", return_value=None):
            gobuster.scan("https://example.com", args=["dir", "-u", "https://example.com", "-q"], use_proxy=True)
    env = mock_run.call_args.kwargs.get("env") or {}
    assert env.get("HTTP_PROXY") == "http://127.0.0.1:18080"
    assert "secret" not in str(env)
```


For gobuster: update `_probe_exclude_length` to accept optional `env` / use `urllib.request.ProxyHandler` when `HTTP_PROXY` is set. Update `_run` to accept `env: dict | None` and pass `env={**os.environ, **env}` to `subprocess.check_output`.

Pattern for sqlmap:

```python
def scan(target, args=None, use_proxy: bool = False, proxy_protocol: str = "http"):
    from tools.proxy_config import resolve_for_tool
    resolved = resolve_for_tool("sqlmap", use_proxy=use_proxy, protocol=proxy_protocol)
    # ... existing arg setup ...
    cmd = ["sqlmap", "-u", url, *args, *resolved["flags"]]
    # run subprocess
    result = {...}
    result["proxy"] = {
        "enabled": use_proxy,
        "protocol": proxy_protocol,
        "mode": resolved["mode"],
        "note": resolved["note"],
    }
    return result
```

Repeat for listed wrappers. For `mode == "unsupported"`, do not add flags; still attach `proxy` metadata with note.

- [ ] **Step 2: Run `pytest tests/test_proxy_wrappers.py -v` — expect FAIL**

- [ ] **Step 3: Implement wrapper changes**

- [ ] **Step 4: Run `pytest tests/test_proxy_wrappers.py tests/test_wrappers_fixes.py -v` — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add src/tools/wrappers/*.py tests/test_proxy_wrappers.py
git commit -m "$(cat <<'EOF'
feat(proxy): wire scanner wrappers to local proxy resolve

EOF
)"
```

---

### Task 4: Propagate flags through Celery + API

**Files:**
- Modify: `src/orchestrator/tasks.py`
- Modify: `src/orchestrator/dashboard.py`
- Modify: `tests/test_dashboard_api.py`
- Create: `tests/test_tasks_proxy_kwargs.py`

**Interfaces:**
- Change: `build_phase_workflow(phase_name, tools_list, target, parallel=False, use_proxy=False, proxy_protocol="http")`
- Change each `run_*_task(self, target, args=None, use_proxy=False, proxy_protocol="http")` for proxy-capable tools
- Change: `_run_playbook_job(job_id, target, playbook, use_proxy=False, proxy_protocol="http")`
- Change: `api_run()` reads `use_proxy` / `proxy_protocol` from JSON body
- Produce: `GET /api/proxy/status` → `{"configured": bool}` only (never username/password)

- [ ] **Step 1: Write failing API/task tests**

```python
def test_api_run_accepts_proxy_flags(client, monkeypatch):
    # monkeypatch _run_playbook_job / threading so no real celery
    resp = client.post("/api/run", json={"target": "example.com", "use_proxy": True, "proxy_protocol": "http"})
    assert resp.status_code == 200
    # assert job record stored use_proxy True


def test_api_run_defaults_proxy_off(client):
    resp = client.post("/api/run", json={"target": "example.com"})
    assert resp.status_code == 200


def test_build_phase_workflow_passes_kwargs_without_secrets(monkeypatch):
    from orchestrator.tasks import build_phase_workflow
    wf = build_phase_workflow(
        "exploitation",
        [{"tool": "sqlmap", "args": ["--batch"]}],
        "example.com",
        use_proxy=True,
        proxy_protocol="http",
    )
    # Inspect signature args: only target, args, use_proxy, proxy_protocol
    sig = wf.tasks[0] if hasattr(wf, "tasks") else wf
    # Celery immutable signature: ensure no password in repr(sig)
    assert "OXYLABS" not in repr(sig)
    assert "password" not in repr(sig).lower()


def test_proxy_status_no_secrets(client, monkeypatch):
    monkeypatch.setenv("OXYLABS_PROXY_USERNAME", "u")
    monkeypatch.setenv("OXYLABS_PROXY_PASSWORD", "secret")
    data = client.get("/api/proxy/status").get_json()
    assert data == {"configured": True}
    assert "secret" not in str(data)
```

Before submitting Celery work when `use_proxy` is True, call `ensure_local_proxy()`; if not healthy, set job failure or log ERROR and continue with `use_proxy=False` only if product choice is fail-open — **spec prefers clear error**: fail the playbook job with redacted message `"local proxy forwarder unhealthy"`.

- [ ] **Step 2: Run tests — expect FAIL**

- [ ] **Step 3: Implement tasks + dashboard changes**

Example task:

```python
def run_sqlmap_task(self, target, args=None, use_proxy=False, proxy_protocol="http"):
    self.update_state(state="STARTED", meta={"status": "SQLMap..."})
    return sqlmap.scan(target, args, use_proxy=use_proxy, proxy_protocol=proxy_protocol)
```

`build_phase_workflow` for each proxy-capable tool:

```python
task_list.append(run_sqlmap_task.si(target, args, use_proxy, proxy_protocol))
```

`api_run` body parsing:

```python
use_proxy = bool(body.get("use_proxy", False))
proxy_protocol = body.get("proxy_protocol") or "http"
if proxy_protocol not in ("http", "https", "socks5h"):
    return jsonify({"error": "invalid proxy_protocol"}), 400
```

- [ ] **Step 4: Run `pytest tests/test_dashboard_api.py tests/test_tasks_proxy_kwargs.py tests/test_proxy_config.py -v` — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add src/orchestrator/tasks.py src/orchestrator/dashboard.py tests/test_dashboard_api.py tests/test_tasks_proxy_kwargs.py
git commit -m "$(cat <<'EOF'
feat(proxy): propagate use_proxy through api and celery

EOF
)"
```

---

### Task 5: Worker env / Kubernetes / Compose wiring

**Files:**
- Modify: `k8s/configmap.yaml`
- Modify: `k8s/secrets.yaml` (placeholder empty keys only — do **not** put real Oxylabs credentials)
- Modify: `k8s/worker-deployment.yaml`
- Modify: `docker/docker-compose.yml` (ensure worker `env_file: ../.env` already covers new keys)
- Modify: `helm/firebreak/values.yaml` (document `existingSecret` keys; no plaintext passwords)

**Interfaces:**
- ConfigMap keys: `OXYLABS_PROXY_HOST`, `OXYLABS_PROXY_PORT`, `OXYLABS_PROXY_PROTOCOL`, `FIREBREAK_LOCAL_PROXY_HOST`, `FIREBREAK_LOCAL_PROXY_PORT`
- Secret keys: `OXYLABS_PROXY_USERNAME`, `OXYLABS_PROXY_PASSWORD` (empty placeholders in checked-in example Secret, or omit values and document `kubectl create secret`)

- [ ] **Step 1: Update ConfigMap**

```yaml
  OXYLABS_PROXY_HOST: pr.oxylabs.io
  OXYLABS_PROXY_PORT: "7777"
  OXYLABS_PROXY_PROTOCOL: http
  FIREBREAK_LOCAL_PROXY_HOST: "127.0.0.1"
  FIREBREAK_LOCAL_PROXY_PORT: "18080"
```

- [ ] **Step 2: Wire worker Deployment envFrom / secretKeyRef** for the seven variables. Do not add Oxylabs secrets to the orchestrator Deployment.

- [ ] **Step 3: Document secret creation** in a short comment at top of `k8s/secrets.yaml` or in `.env.example` only:

```bash
kubectl -n firebreak create secret generic firebreak-secrets \
  --from-literal=OXYLABS_PROXY_USERNAME='...' \
  --from-literal=OXYLABS_PROXY_PASSWORD='...' \
  --dry-run=client -o yaml | kubectl apply -f -
```

Never commit the real password.

- [ ] **Step 4: Commit**

```bash
git add k8s/configmap.yaml k8s/worker-deployment.yaml k8s/secrets.yaml helm/firebreak/values.yaml .env.example
git commit -m "$(cat <<'EOF'
chore(k8s): wire oxylabs proxy env to workers only

EOF
)"
```

---

### Task 6: Scaffold React + Vite frontend

**Files:**
- Create: `frontend/package.json`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/index.html`
- Create: `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/styles/tokens.css`, `frontend/src/styles/global.css`
- Create: `frontend/src/api/client.ts`, `frontend/src/api/socket.ts`
- Modify: `src/orchestrator/dashboard.py` (`index` serves SPA)
- Modify: `.gitignore` (ignore `frontend/node_modules`, keep built assets policy: build in Docker; optionally gitignore `src/orchestrator/static/app` and generate in CI)

**Interfaces:**
- Vite `base: '/static/app/'` and `build.outDir` → `../src/orchestrator/static/app`
- Flask:

```python
from flask import send_from_directory

STATIC_APP = Path(__file__).resolve().parent / "static" / "app"

@app.route("/")
def index():
    return send_from_directory(STATIC_APP, "index.html")

@app.route("/<path:path>")
def spa_fallback(path):
    # do not capture /api, /status, /results, /metrics, /health, /ready, /socket.io
    candidate = STATIC_APP / path
    if candidate.is_file():
        return send_from_directory(STATIC_APP, path)
    return send_from_directory(STATIC_APP, "index.html")
```

Register API routes before the SPA catch-all. Keep Metasploit blueprint prefixes working.

- [ ] **Step 1: Scaffold with Vite React-TS**

```bash
cd frontend && npm create vite@latest . -- --template react-ts
npm install socket.io-client
```

- [ ] **Step 2: Configure dark tactical tokens** in `tokens.css`:

```css
:root {
  --bg-0: #07090d;
  --bg-1: #0d121a;
  --line: #1c2736;
  --text: #d7e0ea;
  --muted: #8b9bb0;
  --cyan: #3de0c6;
  --amber: #f0b429;
  --red: #ff5c5c;
  --font-display: "Orbitron", "Segoe UI", sans-serif;
  --font-mono: "IBM Plex Mono", ui-monospace, monospace;
}
```

Load fonts via `@fontsource` packages or Google Fonts link in `index.html` (Orbitron + IBM Plex Mono). No Inter/Roboto/Arial as primary.

- [ ] **Step 3: Implement `api/client.ts`**

```typescript
export type RunRequest = {
  target: string;
  use_proxy?: boolean;
  proxy_protocol?: "http" | "https" | "socks5h";
};

export async function runPlaybook(body: RunRequest) {
  const res = await fetch("/api/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json() as Promise<{ task_id: string; target: string; state: string }>;
}

export async function getStatus(taskId: string) {
  const res = await fetch(`/status/${taskId}`);
  return res.json();
}

export async function getResults(target: string) {
  const res = await fetch(`/results?target=${encodeURIComponent(target)}`);
  return res.json();
}

export async function getProxyStatus() {
  const res = await fetch("/api/proxy/status");
  return res.json() as Promise<{ configured: boolean }>;
}
```

- [ ] **Step 4: Smoke-build**

```bash
cd frontend && npm run build
```

Expected: assets under `src/orchestrator/static/app/`

- [ ] **Step 5: Commit**

```bash
git add frontend src/orchestrator/dashboard.py src/orchestrator/static/app .gitignore
git commit -m "$(cat <<'EOF'
feat(ui): scaffold vite react operator console shell

EOF
)"
```

---

### Task 7: Mission Launch + Event Log views

**Files:**
- Create: `frontend/src/views/MissionLaunch.tsx`
- Create: `frontend/src/views/EventLog.tsx`
- Create: `frontend/src/components/ProxyToggle.tsx`
- Create: `frontend/src/components/StatusPulse.tsx`
- Create: `frontend/src/hooks/useMission.ts`
- Create: `frontend/src/hooks/useEventLog.ts`
- Optional: `frontend/src/__tests__/MissionLaunch.test.tsx` (Vitest)

**Interfaces:**
- Mission Launch posts `{ target, use_proxy, proxy_protocol }` via `runPlaybook`
- Polls `getStatus(taskId)` every 2s while state is `PENDING`/`STARTED`/`RUNNING`
- Event Log subscribes to Socket.IO `log` events; filter by level / substring `proxy_skipped`
- Proxy toggle never renders password fields; shows `configured` badge from `/api/proxy/status`

- [ ] **Step 1: Implement Mission Launch UI** — brand `Firebreak` as hero signal; target input (empty default); proxy toggle; protocol select default `http`; Run CTA; task id + phase list.

- [ ] **Step 2: Implement Event Log** with enter animation on new rows (CSS `@keyframes` slide/fade).

- [ ] **Step 3: Add Vitest test** that `runPlaybook` is called with `use_proxy: true` when toggle on (mock fetch).

- [ ] **Step 4: Build + manual check against Flask** (`flask` or docker orchestrator).

- [ ] **Step 5: Commit**

```bash
git add frontend
git commit -m "$(cat <<'EOF'
feat(ui): add mission launch and live event log

EOF
)"
```

---

### Task 8: Findings + Exploit Ops + Console

**Files:**
- Create: `frontend/src/views/Findings.tsx`
- Create: `frontend/src/views/ExploitOps.tsx`
- Create: `frontend/src/views/MsfConsole.tsx`
- Create: `frontend/src/components/ResultCard.tsx`
- Create: `frontend/src/components/ConfirmDialog.tsx`
- Modify: `frontend/src/App.tsx` (nav between views)
- Modify/remove: `src/orchestrator/templates/index.html` (stop serving Jinja dashboard; keep file only if tests still reference it — update tests to SPA or delete template)

**Interfaces:**
- Findings: `getResults(target)` → cards with `tool`, `phase`, `timestamp`, text body via `textContent` / React text nodes only; raw JSON in `<pre>`
- Exploit Ops: existing Metasploit REST paths (`/api/metasploit/...`)
- Console: Socket.IO events `msf_console_create|write|read|destroy`
- ConfirmDialog for stop job / close session

- [ ] **Step 1: Port Findings with text-safe rendering** (no `dangerouslySetInnerHTML`)

- [ ] **Step 2: Port module search/run, jobs, sessions**

- [ ] **Step 3: Port MSF console with poll-while-open**

- [ ] **Step 4: Update `tests/test_dashboard.py`** (and related) so they no longer require Jinja markup; assert SPA `index.html` exists under static or that `/` returns 200 with `FIREBREAK` / root div.

- [ ] **Step 5: Commit**

```bash
git add frontend src/orchestrator tests
git commit -m "$(cat <<'EOF'
feat(ui): port findings, exploit ops, and msf console

EOF
)"
```

---

### Task 9: Docker multi-stage build + K8s image notes

**Files:**
- Modify: `docker/orchestrator.Dockerfile`
- Modify: `Dockerfile.orchestrator.prod` (if still used)
- Modify: `k8s/orchestrator-deployment.yaml` (document single replica for Socket.IO)

**Interfaces:**
- Stage `frontend-build`: `node:22-alpine`, `npm ci && npm run build`
- Final stage copies `src/orchestrator/static/app` into image
- Fail build if `static/app/index.html` missing

Example Dockerfile stages:

```dockerfile
FROM node:22-alpine AS frontend
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS runtime
# ... existing python deps ...
COPY --from=frontend /path/to/static/app /app/src/orchestrator/static/app
```

Adjust paths to match repo layout used by the existing Dockerfile (`COPY` roots).

- [ ] **Step 1: Update Dockerfile and build**

```bash
docker build -f docker/orchestrator.Dockerfile -t firebreak-orchestrator:latest .
```

Expected: success; image contains SPA assets.

- [ ] **Step 2: Commit**

```bash
git add docker/orchestrator.Dockerfile Dockerfile.orchestrator.prod k8s/orchestrator-deployment.yaml
git commit -m "$(cat <<'EOF'
build(orchestrator): multi-stage vite assets into image

EOF
)"
```

---

### Task 10: End-to-end verification checklist

**Files:** none required (ops verification)

- [ ] **Step 1: Set local `.env`** with rotated Oxylabs credentials (never commit).

- [ ] **Step 2: Start stack / port-forward**

```bash
kubectl port-forward -n firebreak service/orchestrator-service 5000:5000
# or docker compose up
```

- [ ] **Step 3: UI checks**
  - `/` shows dark tactical Firebreak mission launch
  - Proxy toggle off → run succeeds without proxy metadata `local_proxy`
  - Proxy toggle on → Event Log shows proxy mode / skips; no password in logs
  - Findings / Exploit Ops / Console usable

- [ ] **Step 4: Full pytest**

```bash
pytest -q
```

Expected: all green.

- [ ] **Step 5: Final commit only if checklist fixes were needed**

---

## Spec coverage (self-review)

| Spec requirement | Task |
| --- | --- |
| Per-run toggle default off | 1, 4, 7 |
| All compatible tools + best-effort skip | 1, 3 |
| HTTP default; http/https/socks5h allowed | 1, 4 |
| Local credential-isolating forwarder | 2 |
| No secrets in Celery/argv/UI/git | 1–5, 7 |
| Worker-only K8s secrets + `.env.example` | 1, 5 |
| `POST /api/run` flags + optional status | 4 |
| React+Vite full console, dark tactical | 6–8 |
| Docker static assets | 9 |
| Tests without live Oxylabs | 1–4, 10 |
| Out of scope: playbook `when` gating | (excluded) |

## Placeholder / consistency check

- Function names: `resolve_for_tool`, `redact_proxy_url`, `upstream_proxy_url`, `ensure_local_proxy`, `LocalProxyServer`, `runPlaybook` — used consistently across tasks.
- Result metadata key is always `proxy: { enabled, protocol, mode, note }`.
- No TBD/TODO left in executable steps.
