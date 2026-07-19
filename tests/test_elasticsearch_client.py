from orchestrator.elasticsearch_client import ElasticsearchClient


class _FakeES:
    def __init__(self, ping_ok=True):
        self._ping_ok = ping_ok
        self.indexed = []

    def ping(self):
        return self._ping_ok

    def index(self, index, document):
        self.indexed.append((index, document))
        return {"result": "created"}

    def search(self, **kwargs):
        return {"hits": {"hits": [{"_source": {"target": "example.com"}}]}}


def test_failed_ping_disables_client(monkeypatch):
    monkeypatch.setattr(
        "orchestrator.elasticsearch_client.Elasticsearch",
        lambda hosts: _FakeES(ping_ok=False),
    )
    client = ElasticsearchClient(host="http://es:9200")
    assert client.client is None
    assert client.available is False


def test_successful_ping_enables_client(monkeypatch):
    monkeypatch.setattr(
        "orchestrator.elasticsearch_client.Elasticsearch",
        lambda hosts: _FakeES(ping_ok=True),
    )
    client = ElasticsearchClient(host="http://es:9200")
    assert client.available is True
    assert client.search_results(target="example.com") == [{"target": "example.com"}]
