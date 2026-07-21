"""Localhost HTTP forwarder that injects Oxylabs Basic auth upstream."""

from __future__ import annotations

import base64
import errno
import os
import select
import socket
import threading
from typing import Optional
from urllib.parse import urlparse

from tools.proxy_config import redact_proxy_url, upstream_proxy_url


class ProxyForwardError(Exception):
    def __init__(self, message: str):
        super().__init__(redact_proxy_url(message))


class LocalProxyServer:
    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
    ):
        self.host = host or os.getenv("FIREBREAK_LOCAL_PROXY_HOST", "127.0.0.1")
        env_port = os.getenv("FIREBREAK_LOCAL_PROXY_PORT", "18080")
        self.port = port if port is not None else int(env_port)
        self._sock: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._bound_port: Optional[int] = None

    @property
    def address(self) -> tuple[str, int]:
        return self.host, self._bound_port or self.port

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        protocol = os.getenv("OXYLABS_PROXY_PROTOCOL", "http")
        if protocol == "socks5h":
            raise ProxyForwardError(
                "socks5h forwarder not implemented; use http"
            )
        self._stop.clear()
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self.host, self.port))
        self._bound_port = self._sock.getsockname()[1]
        self._sock.listen(128)
        self._sock.settimeout(1.0)
        self._thread = threading.Thread(target=self._serve, name="firebreak-local-proxy", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    def healthy(self) -> bool:
        return bool(
            self._thread
            and self._thread.is_alive()
            and self._bound_port is not None
            and self._sock is not None
        )

    def _serve(self) -> None:
        assert self._sock is not None
        while not self._stop.is_set():
            try:
                client, _addr = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(
                target=self._handle_client,
                args=(client,),
                daemon=True,
            ).start()

    def _handle_client(self, client: socket.socket) -> None:
        upstream = None
        try:
            client.settimeout(30.0)
            header_data = _recv_headers(client)
            if not header_data:
                return
            first_line, headers, rest = _parse_request(header_data)
            method, target, version = _split_request_line(first_line)
            auth = _proxy_authorization_header()
            upstream = _connect_upstream()
            if method.upper() == "CONNECT":
                connect_req = (
                    f"CONNECT {target} HTTP/1.1\r\n"
                    f"Host: {target}\r\n"
                    f"{auth}"
                    f"Proxy-Connection: Keep-Alive\r\n"
                    f"\r\n"
                ).encode()
                upstream.sendall(connect_req)
                resp = _recv_headers(upstream)
                status_line = resp.split(b"\r\n", 1)[0] if resp else b""
                if not resp.startswith(b"HTTP/1.") or b" 200 " not in status_line:
                    # Surface upstream status without leaking credentials.
                    reason = status_line.decode("latin-1", errors="replace") or "empty upstream response"
                    body = f"upstream CONNECT failed: {reason}\n".encode()
                    client.sendall(
                        b"HTTP/1.1 502 Bad Gateway\r\n"
                        b"Content-Type: text/plain\r\n"
                        + f"Content-Length: {len(body)}\r\n\r\n".encode()
                        + body
                    )
                    return
                client.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                _tunnel(client, upstream)
            else:
                # Absolute-form or origin-form HTTP proxy request
                rebuilt = _rebuild_http_request(method, target, version, headers, rest, auth)
                upstream.sendall(rebuilt)
                _tunnel(client, upstream)
        except Exception:
            try:
                client.sendall(b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n")
            except OSError:
                pass
        finally:
            try:
                client.close()
            except OSError:
                pass
            if upstream is not None:
                try:
                    upstream.close()
                except OSError:
                    pass


_singleton: Optional[LocalProxyServer] = None
_singleton_lock = threading.Lock()


def _port_open(host: str, port: int) -> bool:
    """True if something already accepts TCP on host:port."""
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


class _BorrowedProxy:
    """Reference to a forwarder owned by another process (Celery prefork)."""

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self._bound_port = port

    @property
    def address(self) -> tuple[str, int]:
        return self.host, self.port

    def healthy(self) -> bool:
        return _port_open(self.host, self.port)

    def stop(self) -> None:
        return


def ensure_local_proxy() -> LocalProxyServer:
    global _singleton
    with _singleton_lock:
        if _singleton is not None and _singleton.healthy():
            return _singleton  # type: ignore[return-value]
        if _singleton is not None:
            _singleton.stop()
            _singleton = None

        host = os.getenv("FIREBREAK_LOCAL_PROXY_HOST", "127.0.0.1")
        port = int(os.getenv("FIREBREAK_LOCAL_PROXY_PORT", "18080"))

        # Another Celery child may already own the listener — reuse it.
        if port > 0 and _port_open(host, port):
            borrowed = _BorrowedProxy(host, port)
            _singleton = borrowed  # type: ignore[assignment]
            return borrowed  # type: ignore[return-value]

        server = LocalProxyServer(host=host, port=port)
        try:
            server.start()
        except OSError as exc:
            if getattr(exc, "errno", None) == errno.EADDRINUSE and _port_open(host, port):
                borrowed = _BorrowedProxy(host, port)
                _singleton = borrowed  # type: ignore[assignment]
                return borrowed  # type: ignore[return-value]
            raise ProxyForwardError(f"failed to bind local proxy: {exc}") from exc
        _singleton = server
        return _singleton


def _proxy_authorization_header() -> str:
    from tools.proxy_settings import load_credentials

    creds = load_credentials()
    if not creds:
        raise KeyError("proxy credentials not configured")
    user = creds["username"]
    password = creds["password"]
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return f"Proxy-Authorization: Basic {token}\r\n"


def _connect_upstream() -> socket.socket:
    parsed = urlparse(upstream_proxy_url())
    host = parsed.hostname or "pr.oxylabs.io"
    port = parsed.port or 7777
    sock = socket.create_connection((host, port), timeout=30.0)
    sock.settimeout(30.0)
    return sock


def _recv_headers(sock: socket.socket, limit: int = 65536) -> bytes:
    data = b""
    while b"\r\n\r\n" not in data and len(data) < limit:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data += chunk
    return data


def _parse_request(data: bytes) -> tuple[str, list[tuple[str, str]], bytes]:
    header_blob, _, rest = data.partition(b"\r\n\r\n")
    lines = header_blob.decode("iso-8859-1", errors="replace").split("\r\n")
    first = lines[0]
    headers: list[tuple[str, str]] = []
    for line in lines[1:]:
        if ":" not in line:
            continue
        name, value = line.split(":", 1)
        headers.append((name.strip(), value.strip()))
    return first, headers, rest


def _split_request_line(line: str) -> tuple[str, str, str]:
    parts = line.split(" ")
    if len(parts) < 3:
        raise ProxyForwardError(f"malformed request line: {line}")
    return parts[0], parts[1], parts[2]


def _rebuild_http_request(
    method: str,
    target: str,
    version: str,
    headers: list[tuple[str, str]],
    body: bytes,
    auth_header: str,
) -> bytes:
    skip = {"proxy-connection", "proxy-authorization", "connection"}
    kept = [(n, v) for n, v in headers if n.lower() not in skip]
    lines = [f"{method} {target} {version}"]
    for name, value in kept:
        lines.append(f"{name}: {value}")
    lines.append(auth_header.rstrip("\r\n"))
    lines.append("Connection: close")
    lines.append("")
    lines.append("")
    return "\r\n".join(lines).encode("iso-8859-1") + body


def _tunnel(a: socket.socket, b: socket.socket) -> None:
    sockets = [a, b]
    try:
        while True:
            readable, _, errored = select.select(sockets, [], sockets, 60.0)
            if errored or not readable:
                break
            for src in readable:
                dst = b if src is a else a
                try:
                    data = src.recv(65536)
                except OSError as exc:
                    if exc.errno in (errno.ECONNRESET, errno.EPIPE):
                        return
                    raise
                if not data:
                    return
                try:
                    dst.sendall(data)
                except OSError:
                    return
    except Exception:
        return
