"""Worker scaling helpers — no-op outside Kubernetes."""

from __future__ import annotations

import logging
import os
from typing import Any

from utils.redis_utils import get_redis

logger = logging.getLogger(__name__)


class DynamicScaler:
    def __init__(self) -> None:
        self.k8s_api = None
        self.redis = get_redis()
        try:
            from kubernetes import client, config

            try:
                config.load_incluster_config()
            except Exception:
                config.load_kube_config()
            self.k8s_api = client.AppsV1Api()
        except Exception as exc:
            logger.debug("K8s scaler unavailable: %s", exc)

    def scale_workers(
        self,
        queue_name: str = "celery",
        min_replicas: int = 2,
        max_replicas: int = 50,
    ) -> dict[str, Any]:
        try:
            queue_len = int(self.redis.llen(queue_name) or 0)
        except Exception:
            queue_len = 0
        target = min(max_replicas, max(min_replicas, int(queue_len / 10) + 1))
        if self.k8s_api is None:
            logger.info(
                "Scale noop (no k8s): queue=%s len=%s target=%s",
                queue_name,
                queue_len,
                target,
            )
            return {
                "scaled": False,
                "reason": "kubernetes unavailable",
                "queue_len": queue_len,
                "target_replicas": target,
            }
        deployment_name = os.getenv("WORKER_DEPLOYMENT", "cerberus-worker")
        namespace = os.getenv("NAMESPACE", "default")
        try:
            self.k8s_api.patch_namespaced_deployment_scale(
                name=deployment_name,
                namespace=namespace,
                body={"spec": {"replicas": target}},
            )
            return {
                "scaled": True,
                "deployment": deployment_name,
                "target_replicas": target,
                "queue_len": queue_len,
            }
        except Exception as exc:
            logger.error("Failed to scale: %s", exc)
            return {"scaled": False, "error": str(exc), "target_replicas": target}

    @staticmethod
    def shard_nmap(target: str, ports: str, session_id: str) -> list[dict]:
        tasks: list[dict] = []
        if "-" in ports and "," not in ports:
            start_s, end_s = ports.split("-", 1)
            if start_s.isdigit() and end_s.isdigit():
                start, end = int(start_s), int(end_s)
                step = max(1, (end - start) // 20 or 1)
                for p in range(start, end + 1, step):
                    pr = f"{p}-{min(p + step - 1, end)}"
                    tasks.append(
                        {
                            "tool": "nmap",
                            "params": {
                                "target": target,
                                "ports": pr,
                                "shard_id": f"{session_id}_{pr}",
                            },
                        }
                    )
                return tasks
        tasks.append(
            {"tool": "nmap", "params": {"target": target, "ports": ports}}
        )
        return tasks
