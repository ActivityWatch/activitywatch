import pytest
from aw_watcher_categorize.classifier import MultiTierClassifier, CompiledRule


def test_compiled_rule():
    rule = CompiledRule(["Work", "Code"], r"VSCode|PyCharm", ignore_case=True)
    assert rule.matches("VSCode - main.py")
    assert rule.matches("pycharm.exe")
    assert not rule.matches("Spotify")


def test_classifier_hierarchy_deepest_wins():
    server_rules = [
        (["Work"], {"regex": "ActivityWatch", "ignore_case": True}),
        (["Work", "Programming"], {"regex": "ActivityWatch", "ignore_case": True}),
        (["Work", "Programming", "Core"], {"regex": "aw-core", "ignore_case": True}),
    ]

    classifier = MultiTierClassifier(server_rules=server_rules, enable_heuristics=False)

    cat, conf, source, _ = classifier.classify("Chrome", "ActivityWatch GitHub")
    assert cat == ["Work", "Programming"]
    assert source == "server_rule"
    assert conf == 1.0

    cat2, conf2, source2, _ = classifier.classify("Terminal", "aw-core git diff")
    assert cat2 == ["Work", "Programming", "Core"]
    assert source2 == "server_rule"


def test_classifier_heuristics_fallback():
    classifier = MultiTierClassifier(server_rules=[], enable_heuristics=True)

    cat, conf, source, _ = classifier.classify("Slack", "Slack | general")
    assert cat == ["Comms", "Instant Messaging"]
    assert source == "heuristic"
    assert conf == 0.95

    cat_yt, _, source_yt, _ = classifier.classify("Firefox", "YouTube - Watch Video")
    assert cat_yt == ["Media", "Video & Streaming"]
    assert source_yt == "heuristic"


def test_classifier_uncategorized_fallback():
    classifier = MultiTierClassifier(server_rules=[], enable_heuristics=False)

    cat, conf, source, _ = classifier.classify("UnknownApp", "Unknown Title")
    assert cat == ["Uncategorized"]
    assert conf == 0.0
    assert source == "uncategorized"
