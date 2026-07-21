from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote, urlparse

ALLOWED_PROTOCOLS = frozenset({"http", "https", "socks5h"})

_HTTP_TOOL_BUILDERS = {
    "sqlmap": lambda url: {"flags": ["--proxy", url], "env": {}},
    "ffuf": lambda url: {"flags": ["-x", url], "env": {}},
    "gobuster": lambda url: {
        "flags": ["--proxy", url],
        "env": {
            "HTTP_PROXY": url,
            "HTTPS_PROXY": url,
            "http_proxy": url,
            "https_proxy": url,
        },
    },
    "nuclei": lambda url: {"flags": ["-proxy", url], "env": {}},
    "whatweb": lambda url: {
        "flags": [
            "--proxy",
            f"{urlparse(url).hostname}:{urlparse(url).port}",
        ],
        "env": {},
    },
    "nikto": lambda url: {"flags": ["-useproxy", url], "env": {}},
    "hydra": lambda url: {"flags": [], "env": {"HYDRA_PROXY_HTTP": url}},
    "xsstrike": lambda url: {
        "flags": [],
        "env": {
            "HTTP_PROXY": url,
            "HTTPS_PROXY": url,
            "http_proxy": url,
            "https_proxy": url,
        },
    },
}

_SOCKS_UNSUPPORTED = frozenset({"nikto", "whatweb", "xsstrike"})


def credentials_configured() -> bool:
    from tools.proxy_settings import load_credentials

    return load_credentials() is not None


def local_proxy_url(protocol: str = "http") -> str:
    host = os.getenv("FIREBREAK_LOCAL_PROXY_HOST", "127.0.0.1")
    port = os.getenv("FIREBREAK_LOCAL_PROXY_PORT", "18080")
    scheme = "socks5h" if protocol == "socks5h" else "http"
    return f"{scheme}://{host}:{port}"


def upstream_proxy_url() -> str:
    from tools.proxy_settings import load_credentials

    creds = load_credentials()
    if not creds:
        raise KeyError("proxy credentials not configured")
    user = quote(creds["username"], safe="")
    password = quote(creds["password"], safe="")
    host = creds.get("host") or "pr.oxylabs.io"
    port = int(creds.get("port") or 7777)
    protocol = creds.get("protocol") or "http"
    if protocol not in ALLOWED_PROTOCOLS:
        protocol = "http"
    scheme = "socks5h" if protocol == "socks5h" else "http"
    return f"{scheme}://{user}:{password}@{host}:{port}"


def redact_proxy_url(url: str) -> str:
    """Redact userinfo in a URL or any string containing proxy URLs."""
    import re

    def _redact_match(match: re.Match[str]) -> str:
        return f"{match.group(1)}***{match.group(3)}"

    return re.sub(
        r"(://[^:/@\s]+:)([^@/\s]+)(@)",
        _redact_match,
        url,
    )


def resolve_for_tool(
    tool: str, *, use_proxy: bool, protocol: str = "http"
) -> dict[str, Any]:
    protocol = protocol if protocol in ALLOWED_PROTOCOLS else "http"
    if not use_proxy:
        return {
            "mode": "direct",
            "flags": [],
            "env": {},
            "note": None,
            "local_proxy_url": None,
        }
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
    # v1 forwarder speaks HTTP locally; https upstream requests still use local http URL
    if protocol == "https":
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
