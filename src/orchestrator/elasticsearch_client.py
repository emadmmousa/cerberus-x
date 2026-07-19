import logging
import os
from datetime import datetime, timezone

from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

logger = logging.getLogger(__name__)

ELASTICSEARCH_URL = os.environ.get("ELASTICSEARCH_URL", "http://localhost:9200")


class ElasticsearchClient:
    def __init__(self, host: str | None = None):
        self.host = host or ELASTICSEARCH_URL
        self.client = None
        self._connect()

    @property
    def available(self) -> bool:
        return self.client is not None

    def _connect(self) -> None:
        try:
            client = Elasticsearch([self.host])
            if not client.ping():
                logger.warning("Elasticsearch ping failed; disabling client")
                self.client = None
                return
            self.client = client
            logger.info("Connected to Elasticsearch")
        except Exception as exc:
            logger.error("Elasticsearch connection failed: %s", exc)
            self.client = None

    def index_result(self, target, phase, tool, result, job_id=None) -> bool:
        if not self.client:
            return False
        doc = {
            "target": target,
            "phase": phase,
            "tool": tool,
            "result": result,
            "job_id": job_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        try:
            self.client.index(index="cerberus-results", document=doc)
            return True
        except Exception as exc:
            logger.error("Failed to index result: %s", exc)
            return False

    def bulk_index_results(self, results) -> bool:
        if not self.client or not results:
            return False
        actions = [
            {
                "_index": "cerberus-results",
                "_source": {
                    "target": row.get("target"),
                    "phase": row.get("phase"),
                    "tool": row.get("tool"),
                    "result": row.get("result"),
                    "timestamp": row.get("timestamp")
                    or datetime.now(timezone.utc).isoformat(),
                },
            }
            for row in results
        ]
        try:
            success, _failed = bulk(self.client, actions)
            return success > 0
        except Exception as exc:
            logger.error("Bulk index failed: %s", exc)
            return False

    def search_results(self, target=None, phase=None, tool=None, job_id=None, limit=100):
        if not self.client:
            return None
        must = []
        if target:
            must.append({"match": {"target": target}})
        if phase:
            must.append({"match": {"phase": phase}})
        if tool:
            must.append({"match": {"tool": tool}})
        if job_id:
            must.append({"term": {"job_id.keyword": job_id}})
        query = {"bool": {"must": must}} if must else {"match_all": {}}
        try:
            resp = self.client.search(
                index="cerberus-results",
                query=query,
                size=limit,
                sort=[{"timestamp": {"order": "desc"}}],
            )
            return [hit["_source"] for hit in resp["hits"]["hits"]]
        except Exception as exc:
            logger.error("Search failed: %s", exc)
            return None
