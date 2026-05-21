from datetime import datetime, timedelta, timezone

from aw_watcher_cursor_busy.core import BusySample, BusyTracker, CursorBusyWatcher, EVENT_TYPE


class FakeClient:
    client_hostname = "PROJETO2"

    def __init__(self):
        self.created = []
        self.heartbeats = []

    def create_bucket(self, bucket_id, event_type, queued=False):
        self.created.append((bucket_id, event_type, queued))

    def heartbeat(self, bucket_id, event, pulsetime, queued=False, commit_interval=None):
        self.heartbeats.append((bucket_id, event, pulsetime, queued, commit_interval))


def test_busy_sample_schema():
    sample = BusySample(cursor="wait", app="app.exe", title="Window", pid=123)

    assert sample.to_event_data() == {
        "status": "busy",
        "cursor": "wait",
        "app": "app.exe",
        "title": "Window",
        "pid": 123,
    }


def test_tracker_ignores_short_busy_periods():
    tracker = BusyTracker(min_duration=0.5)
    start = datetime(2026, 5, 21, tzinfo=timezone.utc)
    sample = BusySample(cursor="wait", app="app.exe", title="Window", pid=123)

    assert tracker.update(sample, start) == []
    assert tracker.update(sample, start + timedelta(milliseconds=300)) == []
    assert tracker.update(None, start + timedelta(milliseconds=400)) == []


def test_tracker_emits_from_original_start_after_min_duration():
    tracker = BusyTracker(min_duration=0.5)
    start = datetime(2026, 5, 21, tzinfo=timezone.utc)
    sample = BusySample(cursor="appstarting", app="app.exe", title="Window", pid=123)

    assert tracker.update(sample, start) == []
    events = tracker.update(sample, start + timedelta(milliseconds=500))

    assert len(events) == 1
    assert events[0].timestamp == start
    assert events[0].data["cursor"] == "appstarting"


def test_tracker_emits_followup_heartbeats_after_threshold():
    tracker = BusyTracker(min_duration=0.5)
    start = datetime(2026, 5, 21, tzinfo=timezone.utc)
    sample = BusySample(cursor="wait", app="app.exe", title="Window", pid=123)

    tracker.update(sample, start)
    tracker.update(sample, start + timedelta(milliseconds=500))
    events = tracker.update(sample, start + timedelta(seconds=1))

    assert len(events) == 1
    assert events[0].timestamp == start + timedelta(seconds=1)


def test_watcher_creates_bucket_and_sends_heartbeats():
    client = FakeClient()
    watcher = CursorBusyWatcher(client, pulsetime=1.0, min_duration=0.5)
    start = datetime(2026, 5, 21, tzinfo=timezone.utc)
    sample = BusySample(cursor="wait", app="app.exe", title="Window", pid=123)

    watcher.ensure_bucket()
    watcher.process_sample(sample, start)
    emitted = watcher.process_sample(sample, start + timedelta(milliseconds=500))

    assert client.created == [("aw-watcher-cursor-busy_PROJETO2", EVENT_TYPE, False)]
    assert emitted == 1
    assert len(client.heartbeats) == 1
    bucket_id, event, pulsetime, queued, commit_interval = client.heartbeats[0]
    assert bucket_id == "aw-watcher-cursor-busy_PROJETO2"
    assert event.data["status"] == "busy"
    assert pulsetime == 1.0
    assert queued is True
    assert commit_interval == 1.0
