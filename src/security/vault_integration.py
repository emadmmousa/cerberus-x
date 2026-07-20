"""Vault client with soft-fail when Vault/hvac is unavailable."""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)


class VaultClient:
    _instance: Optional["VaultClient"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_client()
        return cls._instance

    def _init_client(self) -> None:
        self._client = None
        self._ok = False
        addr = os.environ.get("VAULT_ADDR", "http://vault:8200")
        token = os.environ.get("VAULT_TOKEN", "")
        if not token:
            logger.info("VAULT_TOKEN unset; Vault client in no-op mode")
            return
        try:
            import hvac

            client = hvac.Client(url=addr, token=token)
            if client.is_authenticated():
                self._client = client
                self._ok = True
                logger.info("Vault client authenticated at %s", addr)
            else:
                logger.warning("Vault auth failed; continuing without Vault")
        except Exception as exc:
            logger.warning("Vault unavailable (%s); continuing without Vault", exc)

    @property
    def available(self) -> bool:
        return bool(self._ok and self._client)

    def get_secret(self, path: str, key: str | None = None) -> Any:
        if not self.available:
            return None
        try:
            secret = self._client.secrets.kv.v2.read_secret_version(path=path)
            data = secret["data"]["data"]
            return data.get(key) if key else data
        except Exception as exc:
            logger.error("Vault read failed: %s", exc)
            return None

    def rotate_dynamic_secret(self, engine_path: str, role: str):
        if not self.available:
            return None
        try:
            return self._client.secrets.database.generate_credentials(name=role)
        except Exception as exc:
            logger.error("Rotation failed: %s", exc)
            return None

    def revoke_on_anomaly(self, secret_path: str) -> None:
        if not self.available:
            return
        try:
            self._client.secrets.kv.v2.delete_metadata_and_versions(path=secret_path)
        except Exception as exc:
            logger.error("Revocation failed: %s", exc)

    def start_auto_rotation(self, interval: int = 900) -> None:
        if not self.available:
            return
        if os.environ.get("CERBERUS_VAULT_AUTO_ROTATE", "false").lower() not in {
            "1",
            "true",
            "yes",
            "on",
        }:
            logger.info("Vault auto-rotation disabled (set CERBERUS_VAULT_AUTO_ROTATE=true)")
            return

        def rotate_loop():
            while True:
                time.sleep(interval)
                for role in ("postgres-role",):
                    self.rotate_dynamic_secret("database", role)
                logger.info("Vault auto-rotation cycle completed")

        threading.Thread(target=rotate_loop, daemon=True).start()
