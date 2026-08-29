import pytest
from aw_watcher_categorize.learner import aggregate_uncategorized, format_duration


def test_format_duration():
    assert format_duration(30) == "0m"
    assert format_duration(90) == "1m"
    assert format_duration(3660) == "1h 1m"
    assert format_duration(7200) == "2h 0m"


def test_aggregate_uncategorized():
    events = [
        {"data": {"app": "Code", "title": "file1.py"}, "duration": 100},
        {"data": {"app": "Code", "title": "file1.py"}, "duration": 200},
        {"data": {"app": "Chrome", "title": "Custom App"}, "duration": 500},
    ]

    aggregated = aggregate_uncategorized(events)
    assert len(aggregated) == 2
    # Should be sorted descending by total duration
    assert aggregated[0]["app"] == "Chrome"
    assert aggregated[0]["duration"] == 500
    assert aggregated[1]["app"] == "Code"
    assert aggregated[1]["duration"] == 300
