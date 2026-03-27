from thermo_mining.steps.foldseek_client import FoldseekClient, summarize_foldseek_hits


class DummyResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_summarize_foldseek_hits_uses_best_tmscore():
    score = summarize_foldseek_hits(
        [
            {"target": "hit1", "tmscore": 0.44},
            {"target": "hit2", "tmscore": 0.81},
        ]
    )

    assert score == 0.81


def test_foldseek_client_posts_search_request(monkeypatch):
    sent = {}

    def fake_post(url, json, timeout):
        sent["url"] = url
        sent["json"] = json
        sent["timeout"] = timeout
        return DummyResponse({"results": [{"target": "hit1", "tmscore": 0.66}]})

    monkeypatch.setattr("requests.post", fake_post)
    client = FoldseekClient(base_url="http://127.0.0.1:8100", timeout_seconds=30)
    payload = client.search_structure("/tmp/p1.pdb", "afdb50", 5, 0.6)

    assert sent["url"].endswith("/search_structure")
    assert payload["results"][0]["tmscore"] == 0.66
