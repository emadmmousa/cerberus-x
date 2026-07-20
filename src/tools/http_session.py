"""
Wrapper around requests.Session that applies evasion headers and delays.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import requests

from tools.waf_evasion import build_evasion_headers, random_delay, with_static_extension


class EvasiveSession:
    """
    A requests.Session wrapper that injects random headers and delays
    based on evasion settings.
    """

    def __init__(self, evasion: Optional[Dict[str, Any]] = None):
        self.evasion = evasion or {}
        self.session = requests.Session()
        self.session.verify = False
        cookies = self.evasion.get("session_cookies") or self.evasion.get("cookies")
        if isinstance(cookies, dict):
            self.session.cookies.update(cookies)
        self._apply_headers()

    def _apply_headers(self) -> None:
        if self.evasion.get("random_headers", False):
            self.session.headers.update(build_evasion_headers(self.evasion))

    def _maybe_delay(self) -> None:
        if self.evasion.get("random_delay_min", 0) > 0:
            random_delay(
                self.evasion["random_delay_min"],
                self.evasion.get("random_delay_max", 1.0),
            )

    def request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        self._maybe_delay()
        if self.evasion.get("static_extension"):
            url = with_static_extension(url)
        # Refresh UA / injection headers each request when rotating.
        if self.evasion.get("rotate_user_agent") or self.evasion.get("header_injection"):
            self.session.headers.update(build_evasion_headers(self.evasion, target=url))
        # Category 2 — prefer POST when method_swap and body present.
        method_u = method.upper()
        if (
            self.evasion.get("method_swap")
            and method_u == "GET"
            and (kwargs.get("data") is not None or kwargs.get("json") is not None)
        ):
            method_u = "POST"
        return self.session.request(method_u, url, **kwargs)

    def get(self, url: str, **kwargs: Any) -> requests.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> requests.Response:
        return self.request("POST", url, **kwargs)

    def put(self, url: str, **kwargs: Any) -> requests.Response:
        return self.request("PUT", url, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> requests.Response:
        return self.request("DELETE", url, **kwargs)

    def patch(self, url: str, **kwargs: Any) -> requests.Response:
        return self.request("PATCH", url, **kwargs)

    def head(self, url: str, **kwargs: Any) -> requests.Response:
        return self.request("HEAD", url, **kwargs)

    def options(self, url: str, **kwargs: Any) -> requests.Response:
        return self.request("OPTIONS", url, **kwargs)

    def close(self) -> None:
        self.session.close()
