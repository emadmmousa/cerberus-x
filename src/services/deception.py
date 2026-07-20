"""Deception / honeypot helpers — soft-fail without Docker socket."""

from __future__ import annotations

import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)


class DeceptionEngine:
    def __init__(self) -> None:
        self._docker = None
        self.network_name = "cerberus-net"
        try:
            import docker

            self._docker = docker.from_env()
        except Exception as exc:
            logger.debug("Docker unavailable for deception: %s", exc)

    def deploy_honeypot(self, service: str = "http", port: int = 8080) -> dict[str, Any]:
        image_map = {
            "ssh": "linuxserver/openssh-server:latest",
            "http": "nginx:alpine",
            "mysql": "mysql:8",
            "smb": "dperson/samba:latest",
        }
        image = image_map.get(service, image_map["http"])
        if self._docker is None:
            fake_id = f"simulated-{uuid.uuid4().hex[:12]}"
            logger.warning(
                "Simulated honeypot %s on port %s (%s) — docker unavailable",
                service,
                port,
                fake_id,
            )
            return {
                "container_id": fake_id,
                "service": service,
                "port": port,
                "simulated": True,
            }
        try:
            container_port = "22/tcp" if service == "ssh" else "80/tcp"
            container = self._docker.containers.run(
                image,
                detach=True,
                ports={container_port: port},
                network=self.network_name,
                environment={"HONEYPOT_TYPE": service},
                restart_policy={"Name": "on-failure"},
                labels={"cerberus.honeypot": "true"},
            )
            return {
                "container_id": container.id,
                "service": service,
                "port": port,
                "simulated": False,
            }
        except Exception as exc:
            logger.error("Failed to deploy honeypot: %s", exc)
            return {"error": str(exc), "service": service, "port": port}

    def teardown(self, container_id: str) -> dict[str, Any]:
        if container_id.startswith("simulated-") or self._docker is None:
            return {"status": "removed", "container_id": container_id, "simulated": True}
        try:
            container = self._docker.containers.get(container_id)
            container.stop()
            container.remove()
            return {"status": "removed", "container_id": container_id}
        except Exception as exc:
            logger.error("Failed to teardown %s: %s", container_id, exc)
            return {"error": str(exc), "container_id": container_id}
