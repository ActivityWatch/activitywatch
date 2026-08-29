import pytest
from aw_watcher_categorize.ai_client import AIClassifierClient, ClassificationResult, LRUCache


def test_lru_cache():
    cache = LRUCache(capacity=2)
    res1 = ClassificationResult(category=["Work"], regex="work", confidence=0.9)
    res2 = ClassificationResult(category=["Media"], regex="media", confidence=0.8)
    res3 = ClassificationResult(category=["Comms"], regex="comms", confidence=0.95)

    cache.put("k1", res1)
    cache.put("k2", res2)
    assert cache.get("k1") == res1
    assert cache.get("k2") == res2

    # Put k3, which should evict k1 (since k2 was accessed most recently)
    cache.put("k3", res3)
    assert cache.get("k1") is None
    assert cache.get("k2") == res2
    assert cache.get("k3") == res3


def test_parse_json_response():
    client = AIClassifierClient(provider="offline")

    valid_json = """
    {
      "category": ["Work", "Programming", "Python"],
      "regex": "python|django",
      "confidence": 0.98,
      "reasoning": "Python dev activity"
    }
    """
    res = client._parse_json_response(valid_json)
    assert res is not None
    assert res.category == ["Work", "Programming", "Python"]
    assert res.regex == "python|django"
    assert res.confidence == 0.98

    # Markdown fence wrapped
    fenced_json = """```json
    {
      "category": "Media > Video > YouTube",
      "regex": "youtube",
      "confidence": 0.95
    }
    ```"""
    res_fenced = client._parse_json_response(fenced_json)
    assert res_fenced is not None
    assert res_fenced.category == ["Media", "Video", "YouTube"]
    assert res_fenced.regex == "youtube"


def test_parse_batch_json_response():
    client = AIClassifierClient(provider="offline")

    batch_json = """
    [
      {"id": 0, "category": ["Work", "Code"], "regex": "vscode", "confidence": 0.95},
      {"id": 1, "category": ["Media", "Music"], "regex": "spotify", "confidence": 0.9}
    ]
    """
    results = client._parse_batch_json_response(batch_json, count=2)
    assert len(results) == 2
    assert results[0] is not None and results[0].category == ["Work", "Code"]
    assert results[1] is not None and results[1].category == ["Media", "Music"]
